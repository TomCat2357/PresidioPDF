
#JSON出力の形式
▌readの出力は                                                                                                         ▌{"metadata":{...},                                                                                                   ▌"text":{"structured":{...},                                                                                          ▌"plain":["xxx","yyy",....]},                                                                                         ▌"detect":{"structured":{...}}}
▌detectの出力は
▌{"metadata":{...},
▌"detect":{"structured":{...},
▌"plain":{...}}}
▌duplicateの出力は
▌{"metadata":{...},
▌"detect":{"structured":{...},                                                                                        ▌"plain":{...}}}                                                                                                      ▌maskで受け取るjsonは                                                                                                 ▌{"metadata":{...},
▌"detect":{"structured":{....}}}                                                                                      ▌とする。これまでhighlightとしていたものは
▌{"detect":{"structured":{...}}}   
