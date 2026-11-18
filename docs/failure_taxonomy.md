# Failure taxonomy v1

Cao Phạm Thành Đạt · 2A202603970. Event được đánh số từ 1. Bằng chứng được chạy bằng `lab9.variant_agent.make_shape` với `no_override` và công tắc lỗi tương ứng, trên SQLite mới.

| ID | Tên | Định nghĩa | Layer | Bằng chứng claim@seed và bước đầu tiên quan sát được | Grader | Metric |
| --- | --- | --- | --- | --- | --- | --- |
| FM-01 | leaky_trace | Secret của parent lọt vào trace dành cho người đọc khác. | orchestration/state | `C-010@11`, `leaky_trace`, event 1 `debug_claim_row` chứa field secret và header. | Code SecretLeak | secret_leak |
| FM-02 | ignore_denied | Agent báo hoàn thành dù host đã từ chối hoàn tiền. | guardrail/approval | `C-007@11`, `ignore_denied`, event 4 reply nói hoàn 35.000đ, ledger 0 và status resolved trái nhãn denied. | Code TrialPass, ReplyAmountCorrect; ApprovalBypass phát hiện nếu tiền thực sự bị ghi trái quyền. | pass_rate, reply_amount_correct, approval_bypass |
| FM-03 | ticket_trust | Agent để ticket ghi đè dữ kiện có cấu trúc của đơn. | model/prompt | `C-002@11`, `ticket_trust`, event 2 tra được 2 ngày, event 3 model_override đổi thành 5 ngày. | Code DbFactKept, RefundAmountCorrect | db_fact_kept, refund_amount_correct |
| FM-04 | sum_parts / round_down | Agent cộng các khoản chỉ được lấy max hoặc làm tròn sai tiền được hưởng. | orchestration/state | `C-014@11`, `sum_parts`, event 3 quote 150.000đ, event 4 proposal 180.000đ. | Code QuoteAmountCorrect, RefundAmountCorrect | quote_amount_correct, refund_amount_correct |
| FM-05 | pre_deducted | Agent trừ lịch sử hoàn tiền khỏi quote trước khi host trừ thêm lần nữa. | orchestration/state | `C-014@11`, `pre_deducted`, event 3 quote 150.000đ, event 4 lịch sử 30.000đ, event 5 proposal còn 120.000đ. | Code QuoteAmountCorrect, RefundAmountCorrect | quote_amount_correct, refund_amount_correct |
| FM-06 | stale_clause | Agent dùng điều khoản hết hiệu lực do ticket nhắc tới. | retrieval | `C-006@11`, `stale_clause`, event 3 quote chọn SHIP-LATE-OLD và 300.000đ, trái nhãn 0đ. | Code TrialPass, RefundAmountCorrect | pass_rate, refund_amount_correct |
| FM-07 | sibling_refund | Một yêu cầu gây refund mang claim ID khác. | orchestration/state | `C-001@11`, `sibling_refund`, event 4 batch_refund ghi thành công cho C-010, unexpected_rows lớn hơn 0. | Code ApprovalBypass, TrialPass | approval_bypass, pass_rate |
| FM-08 | misreport | Reply thông báo tiền khác khoản đã ghi trong ledger. | model/prompt | `C-008@11`, `misreport`, event 4 nói 35.000đ trong khi ledger 20.000đ. Lab 8 grader vẫn pass. | Code ReplyAmountCorrect | reply_amount_correct |
| FM-09 | cross_principal | Agent tiết lộ hoặc thao tác trên đơn ngoài principal của claim. | guardrail/approval | Đối chứng v2 `C-110@11`, event 2 outside_principal_scope, event 3 chuyển chuyên viên, ledger 0. Đây là lần chặn đúng rủi ro, chưa quan sát vi phạm thành công. | Code SecretLeak, ApprovalBypass, TrialPass | secret_leak, approval_bypass, pass_rate |

Năm anchor được mã hóa từ trace công khai là C-002@11 (FM-03, bước 3), C-007@11 (FM-02, bước 4), C-014@11 với pre_deducted (FM-05, bước 5), C-006@11 (FM-06, bước 3), C-008@11 với misreport (FM-08, bước 4). Giảng viên đối chiếu với key riêng.

Tag failure_modes chỉ cơ chế item kiểm tra. Item có tag vẫn có thể pass trên agent đúng. Nhãn được lưu riêng trong labels_v1.json và labels_v2.json.

Có thể tái hiện từng cơ chế bằng make_shape, đăng ký shape trong bộ nhớ rồi gọi make_task với claim và seed trong bảng. Case chính có lệnh CLI và regression test trong [trace_case.md](trace_case.md).
