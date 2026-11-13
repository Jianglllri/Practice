import { EditorView, basicSetup } from "codemirror";
import { python } from "@codemirror/lang-python";
import { indentWithTab } from "@codemirror/commands";
import { indentUnit } from "@codemirror/language";
import { keymap, gutter, GutterMarker } from "@codemirror/view";
import { StateEffect, StateField, RangeSet } from "@codemirror/state";

const toggleBreakpoint = StateEffect.define();
class Breakpoint extends GutterMarker {
  toDOM() { return document.createTextNode("●"); }
}
const marker = new Breakpoint();
const breakpoints = StateField.define({
  create: () => RangeSet.empty,
  update(value, transaction) {
    value = value.map(transaction.changes);
    for (const effect of transaction.effects) {
      if (!effect.is(toggleBreakpoint)) continue;
      const position = effect.value;
      let exists = false;
      value.between(position, position, () => { exists = true; });
      value = value.update(exists
        ? { filter: from => from !== position }
        : { add: [marker.range(position)] });
    }
    return value;
  },
});
const breakpointGutter = gutter({
  class: "breakpoint-gutter",
  markers: view => view.state.field(breakpoints),
  initialSpacer: () => marker,
  domEventHandlers: {
    mousedown(view, line) {
      view.dispatch({ effects: toggleBreakpoint.of(line.from) });
      return true;
    },
  },
});

const input = document.querySelector("#code");
if (input) {
  const editor = new EditorView({
    doc: input.value,
    extensions: [
      breakpoints,
      breakpointGutter,
      basicSetup,
      python(),
      indentUnit.of("    "),
      keymap.of([indentWithTab]),
      EditorView.cspNonce.of(input.dataset.styleNonce),
      EditorView.contentAttributes.of({ "aria-label": "Python 代码编辑器" }),
      EditorView.updateListener.of(update => {
        if (update.docChanged) input.value = update.state.doc.toString();
      }),
    ],
  });
  input.before(editor.dom);
  input.hidden = true;
  connectCustomCase(editor, input);
}

function connectCustomCase(editor, input) {
  const section = document.querySelector(".custom-case");
  if (!section) return;
  const cases = JSON.parse(section.dataset.cases);
  const names = JSON.parse(section.dataset.names);
  const tabs = section.querySelector(".case-tabs");
  const fields = section.querySelector("#case-fields");
  const expectedInput = section.querySelector("#case-expected");
  const result = section.querySelector("#case-result");
  const panel = section.querySelector("#case-trace");
  const state = section.querySelector("#trace-state");
  const runButton = section.querySelector("#case-run");
  const debugButton = section.querySelector("#case-debug");
  const next = section.querySelector("#trace-next");
  const resume = section.querySelector("#trace-continue");
  let active = 0;
  const drafts = cases.map(({ id, expected, ...values }) => {
    const separated = Object.keys(values).length === 1 && Array.isArray(values.args);
    const entries = separated
      ? values.args.map((value, index) => [names[index] ?? `参数 ${index + 1}`, value])
      : Object.entries(values);
    return { id, separated, entries: entries.map(([key, value]) => [key, JSON.stringify(value)]),
      expected: expected === undefined ? "" : JSON.stringify(expected) };
  });
  function showCase(index) {
    active = index;
    result.hidden = panel.hidden = true;
    const draft = drafts[index];
    tabs.replaceChildren();
    drafts.forEach((_, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `Case ${index + 1}`;
      button.setAttribute("aria-pressed", String(index === active));
      button.onclick = () => showCase(index);
      tabs.append(button);
    });
    const add = document.createElement("button");
    add.type = "button";
    add.textContent = "+";
    add.setAttribute("aria-label", "添加用例");
    add.onclick = () => {
      drafts.push({ ...draft, entries: draft.entries.map(entry => [...entry]), expected: "" });
      showCase(drafts.length - 1);
    };
    tabs.append(add);
    fields.replaceChildren();
    expectedInput.value = draft.expected;
    draft.entries.forEach(([name, value], index) => {
      const label = document.createElement("label");
      const field = document.createElement("textarea");
      field.id = `case-field-${index}`;
      label.htmlFor = field.id;
      label.textContent = name;
      field.className = "code";
      field.rows = 2;
      field.value = value;
      field.addEventListener("input", () => {
        draft.entries[index][1] = field.value;
        draft.expected = expectedInput.value = "";
      });
      fields.append(label, field);
    });
  }
  expectedInput.addEventListener("input", () => { drafts[active].expected = expectedInput.value; });
  if (drafts.length) showCase(0);
  else {
    runButton.disabled = debugButton.disabled = true;
    result.hidden = false;
    result.textContent = "这道题没有可用的本地示例。";
  }

  let trace = [];
  let position = 0;
  let tracedCode = "";
  function showStep(index) {
    if (tracedCode !== input.value) {
      state.textContent = "代码已修改，请重新记录调试轨迹。";
      return;
    }
    position = index;
    const snapshot = trace[index];
    if (!snapshot) {
      state.textContent = "已到轨迹末尾。";
      return;
    }
    const line = editor.state.doc.line(snapshot.line);
    editor.dispatch({ selection: { anchor: line.from }, scrollIntoView: true });
    state.textContent = [
      `第 ${snapshot.line} 行 · 执行前 · ${index + 1}/${trace.length}`,
      ...Object.entries(snapshot.locals).map(([name, value]) => `${name} = ${value}`),
    ].join("\n");
  }

  function isBreakpoint(snapshot) {
    const line = editor.state.doc.line(snapshot.line);
    let found = false;
    editor.state.field(breakpoints).between(line.from, line.from, () => { found = true; });
    return found;
  }
  next.addEventListener("click", () => showStep(position + 1));
  resume.addEventListener("click", () => {
    if (tracedCode !== input.value) return showStep(position);
    const index = trace.findIndex((snapshot, index) => index > position && isBreakpoint(snapshot));
    showStep(index === -1 ? trace.length : index);
  });

  async function run(withTrace) {
    result.hidden = false;
    panel.hidden = true;
    result.textContent = "运行中…";
    runButton.disabled = debugButton.disabled = true;
    try {
      const selected = active;
      const draft = drafts[selected];
      const entries = draft.entries.map(([key, value]) => [key, JSON.parse(value)]);
      const expectedText = expectedInput.value.trim();
      const expected = expectedText ? JSON.parse(expectedText) : null;
      const values = draft.separated ? { args: entries.map(([, value]) => value) } : Object.fromEntries(entries);
      const form = new URLSearchParams({
        token: input.form.elements.token.value,
        id: input.form.elements.id.value,
        code: input.value,
        case: JSON.stringify({ ...values, id: draft.id, expected }),
        trace: withTrace ? "1" : "0",
      });
      tracedCode = input.value;
      const response = await fetch("/custom-case", { method: "POST", body: form });
      if (!response.ok) throw new Error(`运行请求失败（${response.status}）`);
      const data = await response.json();
      if (selected !== active) return;
      if (data.error) throw new Error(data.error);
      result.textContent = `实际输出  ${data.actual}\n预期结果  ${expectedText || "未填写"}`;
      if (data.limitReached) result.textContent += "\n调试轨迹仅保留前 250 步。";
      trace = data.trace;
      if (withTrace && trace.length) {
        panel.hidden = false;
        const first = tracedCode === input.value ? trace.findIndex(isBreakpoint) : -1;
        showStep(first < 0 ? 0 : first);
      }
    } catch (error) {
      result.textContent = error.message;
    } finally {
      runButton.disabled = debugButton.disabled = false;
    }
  }
  runButton.addEventListener("click", () => run(false));
  debugButton.addEventListener("click", () => run(true));
}
