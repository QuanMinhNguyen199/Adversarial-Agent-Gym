# Adversarial Agent Gym

[![English](https://img.shields.io/badge/lang-English-2563eb)](README.md)
[![Tiếng Việt](https://img.shields.io/badge/lang-Ti%E1%BA%BFng%20Vi%E1%BB%87t-dc2626)](README.vi.md)

Adversarial Agent Gym is an AI security evaluation prototype. It tests whether an
AI assistant can complete a useful task without following harmful instructions
hidden in content. All company data is fictional. No real document is accessed
and no real email is sent.

## Why I built it

AI assistants can read documents and use tools for users. This is useful, but it
also creates security risks. I built this project to demonstrate a simple,
repeatable way to test an AI agent before workplace use.

## What is prompt injection?

Prompt injection happens when harmful instructions are hidden inside content that
an AI assistant is asked to read. The attacker hopes the AI will trust those
instructions and perform an unsafe action.

In this project, an employee asks an AI assistant for help with an IT issue. A
malicious instruction in an old vendor comment tries to make the AI read private
salary information and send it outside the company.

## How it works

```text
YAML scenario
→ AI agent performs the task
→ tool actions are recorded
→ evaluator checks clear pass/fail rules
→ Streamlit displays the result
```

Document access and email delivery are mocked, so they never reach real systems.

## Possible results

- **Secure completion:** the agent stayed safe and completed the task.
- **Compromised:** the agent performed a forbidden action.
- **Over-refusal / safe failure:** the agent stayed safe but did not finish the
  harmless request.

ASR means the percentage of successful attacks. STCR means the percentage of tasks
completed both safely and correctly.

## Install and run

Python 3.10 or newer is recommended.

```powershell
git clone https://github.com/QuanMinhNguyen199/Adversarial-Agent-Gym.git
cd Adversarial-Agent-Gym
python -m pip install -r requirements.txt
```

Create a `.env` file:

```dotenv
OPENAI_API_KEY=your-api-key
```

Do not commit this key. Start the dashboard:

```powershell
python -m streamlit run streamlit_app.py
```

## How to run an evaluation

1. Select the YAML task.
2. Select a model.
3. Choose the number of episodes. Use 5 for a quick check and 20 or more for a
   more useful comparison.
4. Enter an output name such as `test1.jsonl`.
5. Click **Start** and wait for the runner to finish.
6. Review the percentages and select an episode to inspect its tool calls.
7. Open `runs/test1.debug.txt` in VS Code to see failure reasons, tool arguments,
   mock results, and the final response.

Model requests consume API quota, but all tools remain simulated. When comparing
models, use the same YAML task and episode count.

## Run automated tests

These tests check the evaluator and mocked tools without calling a model:

```powershell
python -m unittest -v
```

## Main files

| File | Purpose |
| --- | --- |
| `adversarial_enterprise_it_task.yaml` | Defines the agent, attack, and safety rules |
| `run_task.py` | Runs model episodes |
| `evaluator.py` | Checks recorded actions |
| `mock_tools.py` | Simulates documents and email |
| `streamlit_app.py` | Displays and starts evaluations |
| `test_runtime.py` | Tests the evaluation logic |

## Limitations and responsible use

The project currently has one main helpdesk scenario and supports OpenAI models.
It is an evaluation prototype, not a production security control or a complete
reinforcement-learning training system. Use it only for authorized AI safety
testing. Never add real employee data, credentials, or private documents.
