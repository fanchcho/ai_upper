# 权威 run 43600186928（7476558）3.8.10 job 结论

job id: 132463066925  conclusion: failure  failed step: 18 Full integration run
log line 678 标注: [6/6] Target runtime smoke

## 失败调用链（GitHub check-run annotation，公开可读）
L687 |  | Process completed with exit code 1.
L686 | run.log (build.py --run exit 1) | File "qt_compat.py", line 114, in utils.qt_compat._QtModule.__getattr__
L685 | run.log (build.py --run exit 1) | File "web_shell_window.py", line 42, in init mvvm.views.web_shell_window
L684 | run.log (build.py --run exit 1) | File "deva_web.py", line 66, in deva_web._create_window
L683 | run.log (build.py --run exit 1) | File "deva_web.py", line 116, in deva_web.run
L682 | run.log (build.py --run exit 1) | File "deva_web.py", line 154, in deva_web.main
L681 | run.log (build.py --run exit 1) | File "D:\a\ai_upper\ai_upper\dist\ai_upper\ai_upper.exe", line 4, in <module>
L680 | run.log (build.py --run exit 1) | File "<string>", line 429, in _ai_upper_run
L679 | run.log (build.py --run exit 1) | File "qt_compat.py", line 112, in utils.qt_compat._QtModule.__getattr__
L678 | run.log (build.py --run exit 1) | [6/6] Target runtime smoke
