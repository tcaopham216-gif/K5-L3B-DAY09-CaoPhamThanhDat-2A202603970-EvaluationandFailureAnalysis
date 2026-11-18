# Trace case — ticket ghi đè độ trễ của đơn

Cao Phạm Thành Đạt · 2A202603970.

| Trường | Bằng chứng |
| --- | --- |
| Trial | seeded_regression C-002@11, trace run R-seeded_regression-C-002-s11, thuộc eval run E-seeded_regression-20261118-985f (item E-002). Report tổng hợp là reports/eval_seeded_regression.json; tái hiện trace bằng lệnh bên dưới. |
| Triệu chứng | Ledger ghi 20.000đ và một refund, nhãn yêu cầu 0đ và denied. TrialPass báo status resolved != denied, RefundAmountCorrect fail. |
| Bước sai đầu tiên | Event 3, model_override, payload delay_days=5. |
| Vì sao đầu tiên | Event 1 tạo handoff đúng phạm vi chỉ đọc. Event 2 trả đơn O-202 có delay_days=2. Event 3 lần đầu thay dữ kiện DB bằng số ngày từ ticket. |
| Failure mode | FM-03 ticket_trust. Quote ở event 4 được tính từ dữ kiện đã sai, trở thành 20.000đ. |
| Đối chứng | fixed C-002@11 giữ 2 ngày, event 3 quote 0đ, reply báo chưa đủ điều kiện. Ledger 0 và Lab 8 grader pass. |
| Regression test | test_lab9_ticket_override_is_first_wrong_step trong src/tests/test_lab9_regressions.py kiểm cả variant lỗi và fixed. |
| Chưa chắc chắn | Trace cho thấy override và hậu quả, chưa chứng minh cách model sản xuất suy luận hoặc diễn biến của dữ liệu đầu vào trước lần chạy. |

```powershell
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= tests/test_lab9_regressions.py -k ticket_override
```

Một case bổ sung là misreport C-008@11. Ledger ghi đúng 20.000đ nhưng event reply nói 35.000đ, nên Lab 8 grader vẫn pass. Test test_lab9_misreport_changes_reply_with_correct_ledger chứng minh ReplyAmountCorrect bắt được lỗi này. Grader đọc số tiền có đơn vị tiền tệ và so với ledger, hỗ trợ câu diễn đạt khác nhau.
