# Spec: `run_agent()`

**File:** `agent.py`
**Status:** Partially pre-filled — complete the two blank fields before implementing

---

## Purpose

Orchestrate a single conversational turn for the Plant Advisor agent. Given a user message and the conversation history, call the LLM with available tools, execute any tool calls the LLM requests, and return the final text response.

This is the core of what makes Plant Advisor an *agent* rather than a simple chatbot: the ability to decide which tools to call, use their results to inform its response, and loop until it has everything it needs.

---

## Input / Output Contract

**Inputs:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_message` | `str` | The user's current message |
| `history` | `list` | Gradio conversation history — list of `[user_msg, assistant_msg]` pairs |

**Output:** `str`

The agent's final text response for this turn. Should never be empty — if something goes wrong, return a user-readable fallback message.

---

## Design Decisions

*Read `specs/system-design.md` (especially the "How the Groq Tool Calling API Works" section) before reviewing these. Complete the two blank fields before writing any code.*

---

### Messages list structure

The messages list must start with the system prompt, then replay the conversation
history, then add the new user message. Gradio history is a list of `[user, assistant]`
pairs — convert each pair to two API-format dicts:

```python
messages = [{"role": "system", "content": SYSTEM_PROMPT}]

for user_msg, assistant_msg in history:
    messages.append({"role": "user", "content": user_msg})
    if assistant_msg:
        messages.append({"role": "assistant", "content": assistant_msg})

messages.append({"role": "user", "content": user_message})
```

---

### Initial LLM call

Pass the model, the messages list, the tool definitions, and `tool_choice="auto"`
so the LLM can decide whether to call a tool or respond directly:

```python
response = client.chat.completions.create(
    model=LLM_MODEL,
    messages=messages,
    tools=TOOL_DEFINITIONS,
    tool_choice="auto",
)
```

---

### Detecting tool calls in the response

The response object has a `choices` list. Index 0 gives the assistant message.
Check its `tool_calls` attribute — if it's truthy, the LLM wants to call tools:

```python
assistant_message = response.choices[0].message

if not assistant_message.tool_calls:
    # No tool calls — LLM has a final answer
    ...
```

---

### Appending the assistant message

When there are tool calls, append the full assistant message object to `messages`
**before** appending any tool results. The API requires this ordering — a tool
result message must immediately follow the assistant message that requested it:

```python
messages.append(assistant_message)  # must come first
```

---

### Executing and appending tool results

For each tool call, extract the name and arguments, call `dispatch_tool()`, and
append the result as a `"tool"` role message. The `tool_call_id` links this result
back to the specific tool call that requested it:

```python
for tool_call in assistant_message.tool_calls:
    tool_name = tool_call.function.name
    tool_args = json.loads(tool_call.function.arguments)
    tool_result = dispatch_tool(tool_name, tool_args)

    messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": tool_result,
    })
```

---

### Loop termination conditions

*The loop should stop when: (a) the LLM returns a response with no tool calls, OR (b) the MAX_TOOL_ROUNDS limit is reached. Describe how you will detect each condition and what you will return in each case.*

The loop terminates under two conditions:
1. No tool calls: Detected by checking if `not assistant_message.tool_calls` evaluates to True. When this happens, we break the loop and return the LLM's final text response.
2. MAX_TOOL_ROUNDS reached: We wrap the loop in a `for _ in range(MAX_TOOL_ROUNDS):` or use a while loop with a counter. If the loop completes its final iteration without breaking, we return a graceful degradation message like "I've checked a few sources but want to make sure I don't give you conflicting advice. Could you clarify your question?" to prevent infinite hanging.

---

### Extracting the final text response

*Once the loop exits because there are no more tool calls, how do you extract the text content from the response object? What field holds the string you should return?*

The final string response is stored in the `content` attribute of the message object. It can be accessed via `assistant_message.content` (which maps to `response.choices[0].message.content`). We should return this string directly to the user.

---

## Implementation Notes

*Fill this in after implementing and testing.*

**Trace of a working agent turn (what tools were called and in what order):**

Query: "How should I care for my calathea?"
Round 1 tool call: lookup_plant({"plant_name": "calathea"})
Round 2 tool call: get_seasonal_conditions({}) 
Final response: A tailored response combining the calathea's specific need for high humidity and moist soil with the current season's specific advice (warning about hot/dry air for summer and recommending extra misting).

**What happens when you ask about a plant that isn't in the database?**

When asked about a missing plant (like a "Bonsai Tree"), the agent calls lookup_plant({"plant_name": "bonsai"}). The tool returns our programmed not-found JSON message. The LLM reads this internal message, gracefully informs the user that its specific database only covers 15 common houseplants, and offers to provide general plant care advice or look up a different plant. It doesn't crash or hallucinate fake data.

**One thing about the tool call API that surprised you:**

The strict ordering requirement for the message history. It isn't enough to just send the tool results back; you absolutely must append the exact assistant message containing the `tool_calls` array first. If you append the tool results directly after the user message, the API loses the context of why the tool was called and throws an error. The conversation history has to perfectly reflect the exact back-and-forth protocol.
