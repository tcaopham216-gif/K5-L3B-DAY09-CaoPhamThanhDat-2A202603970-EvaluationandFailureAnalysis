# Judge audit

Cao Phạm Thành Đạt · 2A202603970. FAIL là lớp dương, vì judge cần tìm lỗi. Số liệu được tính bằng lab9.judge trên CSV replay của đề.

| Tiêu chí | n | κ | Precision | Recall | TP/FP/FN/TN | Đạt FLOORS | Quyết định |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| tone_ok | 100 | 0,757 | 0,857 | 0,800 | 24 / 4 / 6 / 66 | Có | Dùng trong phạm vi tone |
| helpful | 100 | 0,375 | 1,000 | 0,300 | 9 / 0 / 21 / 70 | Không | Loại khỏi gate |

FLOORS yêu cầu κ≥0,6, precision≥0,8, recall≥0,7. Tone có observed fail rate 0,28, Rogan–Gladen hiệu chỉnh thành 0,30. Helpful có observed rate 0,09 và corrected rate 0,30. Helpful bỏ sót 21/30 lỗi, dù precision bằng 1.

| # | Case | Judge | Người | Kết luận audit | Sửa rubric |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | H-008 | PASS | FAIL | Theo người, “em”, “nha” quá suồng sã với khách. | Chỉ rõ đại từ và mức trang trọng cho khiếu nại. |
| 2 | H-017 | PASS | FAIL | Theo người, giọng “bạn ơi… nha” không phù hợp ngữ cảnh đã cho. | Thêm ví dụ ranh giới thân thiện và suồng sã. |
| 3 | H-029 | PASS | FAIL | Theo người, “không cần nhắn thêm” ra lệnh dù mở đầu lịch sự. | Đánh giá cả phát ngôn, gồm quyền tiếp tục liên hệ. |
| 4 | H-042 | FAIL | PASS | Theo người, câu ngắn vẫn đủ thông tin và lịch sự. | Không bắt buộc xin lỗi ở mọi câu. |
| 5 | H-051 | FAIL | PASS | Theo người, từ “refund” được CS LogiX cho phép. | Ghi danh sách thuật ngữ tiếng Anh chấp nhận được. |
| 6 | H-081 | FAIL | PASS | Ghi chú của bộ dữ liệu xác định nhãn người sai do đọc nhầm ticket. Cần người phụ trách nhãn xác minh lại. | Quy trình adjudication khi nhãn và bối cảnh mâu thuẫn, giữ phiên bản dữ liệu cũ để tái hiện calibration. |
| 7 | HL-015 | PASS | FAIL | Theo người và ghi chú ledger, reply 55.000đ nhưng ledger 40.000đ. | Tiền phải được đối chiếu bằng code. |
| 8 | HL-016 | PASS | FAIL | Lời xin lỗi dài không bù được sai tiền, reply 55.000đ trong khi ledger 35.000đ. | Tách tone khỏi tính đúng số tiền. |

Audit dựa trên reply và note công khai. Riêng H-081 chưa có bối cảnh độc lập để tự xác minh lại. CSV được giữ nguyên khi tính các chỉ số trên.

```powershell
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
```

Lệnh tone trả exit 0, helpful trả exit 1 theo ngưỡng. Sau khi sửa rubric cần nhãn người mới và tập held-out mới. Các grader tiền, approval và reply–ledger đều dùng code.
