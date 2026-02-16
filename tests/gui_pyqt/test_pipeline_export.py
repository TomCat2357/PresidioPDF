import fitz

from src.gui_pyqt.services.pipeline_service import PipelineService


def _create_sample_pdf(pdf_path):
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 120), "機密情報1234", fontsize=14)
        page.insert_text((72, 180), "四角指定", fontsize=14)
        doc.save(str(pdf_path))


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

    result = PipelineService.run_export_annotations(detect_result, pdf_path, output_path)
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
    assert any("origin=auto" in content and "entity=PERSON" in content for content in contents)


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
