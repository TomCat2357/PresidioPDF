import fitz
import json
from pathlib import Path

from src.gui_pyqt.services.pipeline_service import PipelineService
from src.ocr.ndlocr_service import NDLOCRService, OCRResult
from src.pdf.pdf_locator import PDFTextLocator
from src.pdf.pdf_text_embedder import PDFTextEmbedder


def _create_sample_pdf(pdf_path):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), "機密情報1234", fontsize=14)
        page.insert_text((72, 180), "四角指定", fontsize=14)
        doc.save(str(pdf_path))


def _create_pdf_with_invisible_text(pdf_path):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), "VISIBLE", fontsize=14)
        page.insert_text((72, 180), "0000000000000", fontsize=72, fill_opacity=0)
        doc.save(str(pdf_path))


def _get_first_image_size(pdf_path):
    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        images = page.get_images(full=True)
        assert images
        xref = images[0][0]
        extracted = doc.extract_image(xref)
        return extracted.get("width", 0), extracted.get("height", 0)


def test_run_read_ignores_invisible_text_blocks(tmp_path):
    pdf_path = tmp_path / "hidden_text.pdf"
    _create_pdf_with_invisible_text(pdf_path)

    result = PipelineService.run_read(pdf_path, include_coordinate_map=False)

    assert result["text"] == [["VISIBLE"]]


def test_pdf_text_locator_ignores_invisible_text(tmp_path):
    pdf_path = tmp_path / "hidden_text_locator.pdf"
    _create_pdf_with_invisible_text(pdf_path)

    with fitz.open(str(pdf_path)) as doc:
        locator = PDFTextLocator(doc)

    assert locator.full_text_no_newlines == "VISIBLE"


def test_run_detect_skips_whitespace_only_model_result(monkeypatch, tmp_path):
    pdf_path = tmp_path / "whitespace_detect.pdf"
    _create_sample_pdf(pdf_path)
    read_result = PipelineService.run_read(pdf_path, include_coordinate_map=False)

    class _FakeAnalyzer:
        def __init__(self, _cfg):
            pass

        def analyze_text(self, _text, _entities):
            return [
                {
                    "start": 0,
                    "end": 1,
                    "entity_type": "PERSON",
                    "text": " ",
                }
            ]

    monkeypatch.setattr("src.analysis.analyzer.Analyzer", _FakeAnalyzer)

    detect_result = PipelineService.run_detect(
        read_result,
        entities=["PERSON"],
        ignore_newlines=True,
        ignore_whitespace=False,
    )

    assert detect_result["detect"] == []


def test_run_detect_current_page_builds_text_only_for_target_page(
    monkeypatch, tmp_path
):
    pdf_path = tmp_path / "current_page_detect.pdf"
    with fitz.open() as doc:
        first_page = doc.new_page(width=595, height=842)
        first_page.insert_text((72, 120), "FIRST_PAGE_SECRET", fontsize=14)
        second_page = doc.new_page(width=595, height=842)
        second_page.insert_text((72, 120), "SECOND_PAGE_TARGET", fontsize=14)
        doc.save(str(pdf_path))

    read_result = PipelineService.run_read(pdf_path, include_coordinate_map=False)
    observed = {"text": None}

    class _FakeAnalyzer:
        def __init__(self, _cfg):
            pass

        def analyze_text(self, text, _entities):
            observed["text"] = text
            start = text.index("SECOND_PAGE_TARGET")
            end = start + len("SECOND_PAGE_TARGET")
            return [
                {
                    "start": start,
                    "end": end,
                    "entity_type": "PERSON",
                    "text": "SECOND_PAGE_TARGET",
                }
            ]

    monkeypatch.setattr("src.analysis.analyzer.Analyzer", _FakeAnalyzer)

    detect_result = PipelineService.run_detect(
        read_result,
        entities=["PERSON"],
        page_filter=[1],
        ignore_newlines=True,
        ignore_whitespace=False,
    )

    assert observed["text"] == "SECOND_PAGE_TARGET"
    assert len(detect_result["detect"]) == 1
    assert detect_result["detect"][0]["start"]["page_num"] == 1
    assert detect_result["detect"][0]["word"] == "SECOND_PAGE_TARGET"


def test_run_export_annotations_creates_pdf_annotations(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    output_path = tmp_path / "annotated.pdf"
    _create_sample_pdf(pdf_path)

    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        text_rect = page.search_for("機密情報1234")[0]

    detect_result = {
        "detect": [
            {
                "word": "機密情報1234",
                "entity": "PERSON",
                "origin": "auto",
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 6},
                "rects_pdf": [[text_rect.x0, text_rect.y0, text_rect.x1, text_rect.y1]],
            },
            {
                "word": "四角指定",
                "entity": "OTHER",
                "origin": "manual",
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 3},
                "mask_rects_pdf": [[68.0, 165.0, 150.0, 190.0]],
            },
        ],
        "text": [["機密情報1234", "四角指定"]],
    }

    result = PipelineService.run_export_annotations(
        detect_result, pdf_path, output_path
    )
    assert result["success"] is True
    assert output_path.exists()
    assert result["annotation_count"] >= 2

    contents = []
    with fitz.open(str(output_path)) as out_doc:
        page = out_doc[0]
        annotations = list(page.annots() or [])
        for annot in annotations:
            contents.append((annot.info or {}).get("content", ""))

    assert len(annotations) > 0
    assert any(
        "origin=auto" in content and "entity=PERSON" in content for content in contents
    )


def test_run_mask_as_image_removes_extractable_text(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    output_path = tmp_path / "masked_image.pdf"
    _create_sample_pdf(pdf_path)

    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        target_rect = page.search_for("機密情報1234")[0]

    detect_result = {
        "detect": [
            {
                "word": "機密情報1234",
                "entity": "PERSON",
                "origin": "manual",
                "manual": True,
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 6},
                "mask_rects_pdf": [
                    [target_rect.x0, target_rect.y0, target_rect.x1, target_rect.y1]
                ],
            }
        ],
        "text": [["機密情報1234", "四角指定"]],
    }

    result = PipelineService.run_mask_as_image(detect_result, pdf_path, output_path)
    assert result["success"] is True
    assert output_path.exists()

    with fitz.open(str(output_path)) as masked_doc:
        extracted_text = "".join(page.get_text().strip() for page in masked_doc)
        assert extracted_text == ""
        assert all(len(page.get_images(full=True)) > 0 for page in masked_doc)


def test_run_mask_as_image_respects_dpi(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    output_low = tmp_path / "masked_image_72.pdf"
    output_high = tmp_path / "masked_image_300.pdf"
    _create_sample_pdf(pdf_path)

    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        target_rect = page.search_for("機密情報1234")[0]

    detect_result = {
        "detect": [
            {
                "word": "機密情報1234",
                "entity": "PERSON",
                "origin": "manual",
                "manual": True,
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 6},
                "mask_rects_pdf": [
                    [target_rect.x0, target_rect.y0, target_rect.x1, target_rect.y1]
                ],
            }
        ],
        "text": [["機密情報1234", "四角指定"]],
    }

    low_result = PipelineService.run_mask_as_image(
        detect_result, pdf_path, output_low, dpi=72
    )
    high_result = PipelineService.run_mask_as_image(
        detect_result, pdf_path, output_high, dpi=300
    )
    assert low_result["success"] is True
    assert high_result["success"] is True

    low_width, low_height = _get_first_image_size(output_low)
    high_width, high_height = _get_first_image_size(output_high)
    assert high_width > low_width
    assert high_height > low_height


def test_run_export_marked_as_image_creates_image_pdf(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    output_path = tmp_path / "marked_image.pdf"
    _create_sample_pdf(pdf_path)

    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        rect = page.search_for("機密情報1234")[0]

    detect_result = {
        "detect": [
            {
                "word": "機密情報1234",
                "entity": "PERSON",
                "origin": "manual",
                "manual": True,
                "start": {"page_num": 0, "block_num": 0, "offset": 0},
                "end": {"page_num": 0, "block_num": 0, "offset": 6},
                "mask_rects_pdf": [[rect.x0, rect.y0, rect.x1, rect.y1]],
            }
        ],
        "text": [["機密情報1234", "四角指定"]],
    }

    result = PipelineService.run_export_marked_as_image(
        detect_result, pdf_path, output_path, dpi=300
    )
    assert result["success"] is True
    assert result["entity_count"] >= 1
    assert output_path.exists()

    with fitz.open(str(output_path)) as marked_doc:
        extracted_text = "".join(page.get_text().strip() for page in marked_doc)
        assert extracted_text == ""
        assert all(len(page.get_images(full=True)) > 0 for page in marked_doc)


def test_pdf_text_embedder_embed_and_remove(tmp_path):
    source_pdf_path = tmp_path / "embed_target.pdf"
    output_pdf_path = tmp_path / "embed_output.pdf"
    _create_sample_pdf(source_pdf_path)

    with fitz.open(str(source_pdf_path)) as doc:
        inserted = PDFTextEmbedder.embed_ocr_results(
            doc,
            {
                0: [
                    {
                        "text": "OCRTXT",
                        "x": 72.0,
                        "y": 240.0,
                        "width": 180.0,
                        "height": 24.0,
                        "page_num": 0,
                        "confidence": 0.9,
                    }
                ]
            },
            font_color=[0, 0, 0],
            opacity=0.0,
        )
        assert inserted == 1
        doc.save(str(output_pdf_path))

    with fitz.open(str(output_pdf_path)) as doc:
        assert "OCRTXT" in doc[0].get_text("text")
        removed = PDFTextEmbedder.remove_ocr_text(doc)
        assert removed == 1
        doc.save(
            str(output_pdf_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP
        )

    with fitz.open(str(output_pdf_path)) as doc:
        assert "OCRTXT" not in doc[0].get_text("text")


def test_run_ocr_and_clear_pipeline(monkeypatch, tmp_path):
    pdf_path = tmp_path / "ocr_pipeline.pdf"
    _create_sample_pdf(pdf_path)

    def _fake_run_ocr_on_page(self, page_pixmap, existing_text_rects, **kwargs):
        _ = page_pixmap
        _ = existing_text_rects
        page_num = int(kwargs.get("page_num", 0))
        return [
            OCRResult(
                text="OCR_WORD",
                x=72.0,
                y=300.0,
                width=120.0,
                height=20.0,
                page_num=page_num,
                confidence=0.8,
            )
        ]

    monkeypatch.setattr(NDLOCRService, "is_available", staticmethod(lambda: True))
    monkeypatch.setattr(NDLOCRService, "run_ocr_on_page", _fake_run_ocr_on_page)

    ocr_settings = {
        "font_color": [0, 0, 0],
        "opacity": 0.0,
        "ocr_before_detect": False,
    }
    ocr_result = PipelineService.run_ocr(
        pdf_path=pdf_path,
        page_filter=[0],
        ocr_settings=ocr_settings,
        dpi=72,
    )
    assert ocr_result["success"] is True
    assert ocr_result["embedded_count"] == 1
    with fitz.open(str(pdf_path)) as doc:
        assert "OCR_WORD" in doc[0].get_text("text")

    clear_result = PipelineService.run_clear_ocr_text(
        pdf_path=pdf_path, page_filter=[0]
    )
    assert clear_result["success"] is True
    assert clear_result["removed_count"] == 1
    with fitz.open(str(pdf_path)) as doc:
        assert "OCR_WORD" not in doc[0].get_text("text")


def _create_fake_ndlocr_layout(base_dir: Path) -> Path:
    (base_dir / "model").mkdir(parents=True, exist_ok=True)
    (base_dir / "config").mkdir(parents=True, exist_ok=True)
    (base_dir / "model" / "deim-s-1024x1024.onnx").write_bytes(b"")
    (base_dir / "model" / "parseq-ndl-16x768-100-tiny-165epoch-tegaki2.onnx").write_bytes(
        b""
    )
    (base_dir / "config" / "ndl.yaml").write_text("", encoding="utf-8")
    (base_dir / "config" / "NDLmoji.yaml").write_text("", encoding="utf-8")

    ocr_path = base_dir / "ocr.py"
    ocr_path.write_text(
        "\n".join(
            [
                "import json",
                "from pathlib import Path",
                "",
                "def process(args):",
                "    src = Path(args.sourceimg)",
                "    out_dir = Path(args.output)",
                "    payload = {",
                "        'contents': [[{'text': 'FAKE', 'box': [1, 2, 10, 8], 'confidence': 0.9}]]",
                "    }",
                "    (out_dir / f'{src.stem}.json').write_text(json.dumps(payload), encoding='utf-8')",
            ]
        ),
        encoding="utf-8",
    )
    return ocr_path


class _FakeDistribution:
    def __init__(self, ocr_path: Path):
        self._ocr_path = ocr_path

    def locate_file(self, _relative_path: Path) -> Path:
        return self._ocr_path


def test_ndlocr_get_distribution_ocr_path_uses_importlib_metadata(monkeypatch, tmp_path):
    ocr_path = _create_fake_ndlocr_layout(tmp_path)

    monkeypatch.setattr(
        "src.ocr.ndlocr_service.importlib_metadata.distribution",
        lambda _name: _FakeDistribution(ocr_path),
    )

    resolved = NDLOCRService._get_distribution_ocr_path()
    assert resolved == ocr_path.resolve()


def test_ndlocr_is_available_returns_true_with_distribution_layout(
    monkeypatch, tmp_path
):
    ocr_path = _create_fake_ndlocr_layout(tmp_path)

    monkeypatch.setattr(
        "src.ocr.ndlocr_service.importlib_metadata.distribution",
        lambda _name: _FakeDistribution(ocr_path),
    )

    assert NDLOCRService.is_available() is True


def test_ndlocr_get_process_callable_falls_back_to_distribution_path(
    monkeypatch, tmp_path
):
    ocr_path = _create_fake_ndlocr_layout(tmp_path)

    monkeypatch.setattr(
        NDLOCRService,
        "_MODULE_CANDIDATES",
        (("missing.ndlocr.module", "process", "legacy"),),
    )
    monkeypatch.setattr(
        "src.ocr.ndlocr_service.importlib_metadata.distribution",
        lambda _name: _FakeDistribution(ocr_path),
    )

    source_image = tmp_path / "page.png"
    source_image.write_bytes(b"png")

    service = NDLOCRService()
    runner = service._get_process_callable()
    result = runner(str(source_image))

    assert callable(runner)
    assert isinstance(result, list)
    assert result
    first = result[0]
    assert isinstance(first, dict)
    assert first.get("text") == "FAKE"
