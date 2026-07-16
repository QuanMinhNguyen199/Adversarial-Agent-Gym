# AI Security RL Gyms — Future Roadmap

## Tầm nhìn

AI Security RL Gyms là một bộ môi trường và benchmark có thể tái lập để huấn luyện,
red-team và đánh giá AI agent trước các cuộc tấn công prompt injection, data
exfiltration, tool misuse và policy circumvention.

Mục tiêu không chỉ là kiểm tra agent có “trả lời an toàn” hay không, mà đo được agent
đã quan sát gì, gọi tool nào, thay đổi trạng thái môi trường ra sao và có hoàn thành
phần yêu cầu hợp lệ của người dùng hay không.

## Trạng thái hiện tại

Đã có:

- Một task indirect prompt injection trong môi trường Enterprise IT Helpdesk.
- JSON Schema và lệnh validate YAML với đường dẫn lỗi rõ ràng.
- OpenAI runner hỗ trợ multi-step tool calling.
- Mock document/email tools, JSONL trace và debug report.
- Deterministic evaluator tách `security_passed` và `utility_passed`.
- Regression rule/test cho phép safe internal email giải thích payload bị từ chối,
  không còn false over-refusal chỉ vì nhắc restricted document ID.
- Streamlit dashboard và unit tests.
- Catalog 10 payload variants cùng objective, custom vendor-comment input và full
  benchmark theo variant.

Chưa có:

- Human-in-the-loop hoặc nút duyệt từng tool call nhạy cảm.
- Tool authorization thực tế như document ACL hoặc chặn external recipient.
- Replay hoàn chỉnh, provider adapter, confidence interval và CI.
- Reward API hoặc training loop; đây vẫn là evaluation prototype, chưa phải hệ
  thống reinforcement learning hoàn chỉnh.

## Nguyên tắc thiết kế

- Deterministic first: ưu tiên chấm bằng tool call, tham số và state transition.
- Security và utility cùng tồn tại: agent phải tránh hành động nguy hiểm nhưng vẫn
  hoàn thành phần công việc an toàn.
- Trust boundary rõ trong môi trường, không lộ đáp án trong system prompt.
- Không gọi hệ thống thật trong benchmark mặc định; email, tài liệu và ticket đều mock.
- Mọi task phải tái lập được bằng seed, phiên bản model và cấu hình inference.
- Tách biệt task definition, runtime, model adapter và evaluator.
- Báo cáo cả pass rate lẫn nguyên nhân thất bại, không chỉ một điểm tổng hợp.

## Phase 1 — Chuẩn hóa Task Spec và Evaluator (v0.2)

### Mục tiêu

Biến task hiện tại thành một đặc tả có thể mở rộng và chấm tự động mà không cần sửa
code cho từng tình huống.

### Hạng mục

- Bổ sung các operator evaluator chưa có:
  - `ordered_before`, `never_called`
  - state assertions trước và sau episode
- Cải thiện failure reasons để chỉ rõ argument/constraint nào không match, thay vì
  chỉ báo tổng quát “expected matching call, got 0”.

### Definition of Done

- Thêm một task mới mà không sửa evaluator Python.
- YAML sai schema bị từ chối với thông báo dễ hiểu.
- Unit test bao phủ mọi operator chấm điểm.

## Phase 2 — Hoàn thiện Runtime (v0.3)

### Mục tiêu

Đưa runtime hiện tại từ prototype một provider thành hệ thống có thể replay, so sánh
model và kiểm soát execution chặt chẽ.

### Kiến trúc dự kiến

```text
Task YAML
   │
   ▼
Episode Builder ──► Model Adapter ──► Tool Sandbox
   │                    │                  │
   │                    └──── tool calls ──┘
   ▼
Trace Recorder ──► Deterministic Evaluator ──► Report
```

### Hạng mục còn lại

- Tách interface model adapter để bổ sung provider khác và local model.
- Tách hai execution mode:
  - `evaluation`: ghi nhận ý định/tool call để đo năng lực model.
  - `protected`: policy gateway có thể chặn hoặc yêu cầu approval trước side effect.
- Bổ sung tool-level authorization:
  - Document ACL theo user, role và classification.
  - Chuẩn hóa recipient và chặn dữ liệu nhạy cảm gửi ra ngoài domain.
- Thêm human-in-the-loop tùy chọn cho restricted document và external email:
  - `pending_approval`, `approved`, `denied`.
  - Vẫn ghi nhận unsafe request của model dù con người đã chặn side effect.
- Chuẩn hóa trace schema chính thức cho các trường chưa có:
  - message role và model output items
  - raw/normalized arguments
  - environment state hash
  - runner/evaluator version
- Thêm timeout theo episode và giới hạn tool call độc lập với `max_steps`.
- Ghi cả malformed/rejected tool attempts vào trace thay vì chỉ ghi call đã chạy
  qua mock sandbox.
- Bổ sung seed, max tokens và model snapshot vào cấu hình inference.
- Thêm các lệnh CLI còn thiếu:

```bash
ai-sec-gym validate tasks/helpdesk_salary.yaml
ai-sec-gym evaluate runs/latest.jsonl
ai-sec-gym replay runs/latest.jsonl --episode EPISODE_ID
```

### Definition of Done

- Trace có thể replay và cho cùng kết quả evaluator.
- Không lưu secret hoặc nội dung nhạy cảm thật vào log.
- Phân biệt được model an toàn, unsafe attempt bị chặn và side effect đã xảy ra.
- Protected mode không cho một model request đơn lẻ vượt qua policy gateway.

## Phase 3 — Benchmark Prompt Injection (v0.4)

### Mục tiêu

Mở rộng từ một payload thành ma trận attack × placement × obfuscation × objective.

### Đã triển khai bước đầu

- 10 payload variants giữ nguyên salary-exfiltration objective.
- Base, preset, full benchmark và custom payload mode trong Streamlit.
- Trace lưu variant ID, technique, language, difficulty, placement và payload hash.
- Report hỗ trợ ASR/STCR theo variant.
- `benchmark.py` có dry-run mặc định, hiển thị tổng API episodes, từ chối output đã
  tồn tại và chỉ gọi model khi có cờ `--run`.

Hiện variants mới chỉ thay nội dung vendor comment và giữ nguyên objective/evaluator;
placement matrix và objective matrix vẫn chưa triển khai.

### Attack families

- Fake procedure hoặc fake policy update.
- Giả dạng system/developer message.
- Role-play và authority impersonation.
- Context stuffing trong comment hoặc tài liệu dài.
- Instruction chaining qua nhiều tài liệu.
- Payload trong file đính kèm, HTML, Markdown hoặc metadata.
- Multilingual và code-switching.
- Encoded/obfuscated instruction.
- Delayed injection: payload chỉ kích hoạt sau một tool result.
- Cross-ticket và cross-user contamination.

### Placement matrix

- Ticket hiện tại.
- Comment từ người dùng khác.
- Ticket cũ được liên kết tự động.
- File đính kèm.
- Kết quả tìm kiếm nội bộ.
- Tài liệu knowledge base.
- Nội dung email được forward.
- Tool error hoặc tool metadata.

### Security objectives

- Data exfiltration.
- Unauthorized document access.
- Gửi email hoặc tin nhắn không được phép.
- Thay đổi quyền hoặc cấu hình.
- Persistence qua ghi chú/ticket mới.
- Social engineering người dùng tiếp theo.
- Che giấu hành động trong final response.

### Difficulty ladder

- Level 1: payload trực diện, format bất thường.
- Level 2: payload giống quy trình nội bộ.
- Level 3: payload phân tán qua nhiều nguồn.
- Level 4: cần nhiều bước tool-use mới hoàn tất tấn công.
- Level 5: adaptive attacker thay đổi theo hành động của agent.

## Phase 4 — Reward Design cho RL (v0.5)

### Mục tiêu

Chuyển pass/fail thành reward có cấu trúc, phù hợp cho reinforcement learning và
policy optimization nhưng không khuyến khích agent chỉ từ chối mọi thứ.

### Reward proposal

```text
total_reward = utility_reward
             + policy_reward
             + efficiency_reward
             + transparency_reward
             - violation_penalty
```

- `utility_reward`: hoàn thành yêu cầu hợp lệ.
- `policy_reward`: tuân thủ policy và trust boundary.
- `efficiency_reward`: không gọi tool dư thừa.
- `transparency_reward`: giải thích phù hợp khi chặn một hành động.
- `violation_penalty`: phạt rất lớn cho side effect nguy hiểm.

### Guardrails cho reward hacking

- Không cho điểm tối đa nếu agent chỉ từ chối.
- Phân biệt “không gọi tool” với “hoàn thành an toàn”.
- Dùng hidden tests và payload paraphrase.
- Chấm state cuối cùng, không chỉ câu trả lời cuối.
- Giữ violation penalty độc lập với style/verbosity.
- Theo dõi reward component riêng để phát hiện tối ưu lệch.

## Phase 5 — Multi-environment Security Gyms (v0.6)

Mở rộng ngoài Enterprise IT Assistant:

- Helpdesk Gym: ticket, tài liệu, email, reset quyền.
- Developer Gym: repository, issue, CI log, package instructions.
- Finance Gym: invoice, payment approval, vendor onboarding.
- HR Gym: hồ sơ nhân viên, tuyển dụng, payroll.
- Productivity Gym: email, calendar, drive và chat nội bộ.
- CloudOps Gym: dashboard, incident response, secrets và deployment.

Mỗi gym cần:

- Tool contract rõ ràng.
- State machine có thể reset.
- Seed data tổng hợp, không dùng dữ liệu thật.
- Action allowlist và sandbox.
- Task suite gồm benign, adversarial và mixed episodes.

## Phase 6 — Metrics và Báo cáo (v0.7)

### Core metrics

- Policy Violation Rate.
- Unnecessary Tool Access Rate.
- Exfiltration Rate.
- Mean Steps to Completion.
- Variance theo seed và temperature.
- Unsafe Attempt Rate: model yêu cầu hành động bị cấm, kể cả khi gateway chặn.
- Prevented Side-effect Rate: tỷ lệ unsafe attempt bị policy/human chặn thành công.

### Báo cáo bắt buộc

- Điểm tổng và điểm theo attack family.
- Confusion matrix: safe completion, unsafe completion, safe refusal, unsafe refusal.
- So sánh model/prompt/version.
- Confidence interval thay vì chỉ báo cáo một tỷ lệ đơn.
- Tách `over-refusal` thành safe refusal, wrong-tool và incomplete task.

## Phase 7 — CI/CD và Regression Security (v0.8)

- Chạy smoke suite trên mỗi pull request.
- Chạy full benchmark theo lịch.
- Lưu baseline theo model và system prompt version.
- Fail CI nếu ASR tăng hoặc STCR giảm quá threshold.
- Snapshot trace cho các lỗi nghiêm trọng.
- Tự động tạo minimal reproduction task từ episode thất bại.
- Có quarantine cho test nondeterministic, nhưng không xóa failure khỏi báo cáo.

## Phase 8 — Public Benchmark và Community (v1.0)

- Public task schema và task authoring guide.
- Bộ task mẫu có license rõ ràng.
- Leaderboard tách theo model, prompt và tool configuration.
- Quy trình review task chống lộ đáp án và evaluator ambiguity.
- Contribution template và security disclosure policy.
- Dataset card/model card cho từng release.
- Chống benchmark contamination bằng hidden test set và rotating variants.

## Cấu trúc repository mục tiêu

```text
ai-security-rl-gyms/
├── schemas/
│   └── task.schema.json
├── tasks/
│   ├── helpdesk/
│   ├── developer/
│   ├── finance/
│   └── hr/
├── gym/
│   ├── runner/
│   ├── adapters/
│   ├── tools/
│   ├── evaluator/
│   └── reporting/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
├── docs/
│   ├── authoring-guide.md
│   ├── threat-model.md
│   └── evaluation-methodology.md
└── runs/
    └── .gitkeep
```

## Threat model ban đầu

### Tài sản cần bảo vệ

- Dữ liệu nội bộ và dữ liệu cá nhân.
- Quyền gọi tool và side effect.
- Secret, credential và access token.
- Tính toàn vẹn của ticket, email và tài liệu.
- Người dùng hoặc agent ở episode tiếp theo.

### Đối thủ

- Người ngoài kiểm soát nội dung được nhập vào hệ thống.
- Nhân viên nội bộ có quyền hạn thấp.
- Tài liệu hoặc ticket đã bị compromise.
- Tool output bị thao túng.
- Model tự tạo chuỗi hành động ngoài ý định ban đầu.

### Ngoài phạm vi giai đoạn đầu

- Tấn công hạ tầng model/provider.
- Khai thác binary hoặc kernel sandbox.
- Dữ liệu sản xuất và tool side effect thật.
- Đánh giá năng lực cybersecurity tấn công hệ thống thực.

## Backlog ưu tiên gần nhất

1. Đồng bộ policy nghiệp vụ với evaluator: phân biệt unauthorized read và full
   data exfiltration.
2. Tách outcome `over-refusal` thành safe refusal, wrong-tool và incomplete task.
3. Thêm synthetic canary để phát hiện exfiltration chính xác.
4. Định nghĩa trace schema JSONL, run ID và runner/evaluator version.
5. Ghi malformed/rejected tool attempts vào trace.
6. Thêm protected mode với document ACL và external-recipient enforcement.
7. Thêm human approval tùy chọn sau policy gateway cho hành động nhạy cảm.
8. Mở rộng variants sang attachment, tool result và linked document placement.
9. Chạy variants trên nhiều seed, temperature và model snapshot.
10. Thêm confidence interval và model comparison vào report/dashboard.
11. Thêm episode replay và regression fixture từ failure thật.
12. Tách model adapter interface và thêm provider/local model thứ hai.
13. Đóng gói CLI `evaluate`, `replay` và hợp nhất với lệnh `validate` hiện tại.

## Milestone đề xuất

| Milestone | Kết quả chính | Tiêu chí hoàn thành |
|---|---|---|
| M1 — Spec | Schema và operator set hoàn chỉnh | Task mới hợp lệ qua schema và không cần custom scoring code |
| M2 — Runtime | Trace, replay và protected execution | Phân biệt unsafe intent, blocked action và side effect |
| M3 — Benchmark | 50+ task variants | Có ASR/STCR theo attack family |
| M4 — RL Gym | Reward API và resettable env | Dùng được trong training loop |
| M5 — Release | Docs, CI, leaderboard | Public v1.0 có versioned benchmark |

## Tiêu chí chất lượng cho mỗi task mới

- Benign request phải tự nhiên và có ích.
- Payload không đến trực tiếp từ người dùng hiện tại.
- System prompt không lộ chính xác cách phòng thủ.
- Policy nghiệp vụ đủ rõ để xác định hành vi an toàn.
- Có ít nhất một safe completion path.
- Pass/fail dựa trên hành động hoặc state có thể kiểm tra.
- Không dùng semantic flag mơ hồ nếu chưa định nghĩa evaluator.
- Có positive test, negative test và boundary test.
- Payload có provenance và trust boundary rõ trong environment.
- Không chứa secret hoặc dữ liệu cá nhân thật.

## North-star metric

Chỉ số trung tâm của AI Security RL Gyms là **Secure Task Completion Rate**:

> Tỷ lệ episode mà agent vừa hoàn thành đúng yêu cầu hợp lệ, vừa không thực hiện bất
> kỳ hành động vi phạm policy nào.

Chỉ số này ngăn benchmark thưởng cho hai cực đoan: agent làm mọi thứ và bị khai thác,
hoặc agent từ chối mọi thứ để có vẻ an toàn.
