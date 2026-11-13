const form = document.querySelector("form[data-mock-round]");
if (form) {
  const fields = [...form.querySelectorAll("textarea")];
  const draftKey = "mock-interview:" + form.dataset.mockRound;
  try {
    const draft = JSON.parse(sessionStorage.getItem(draftKey) || "{}");
    for (const field of fields) {
      if (typeof draft[field.name] === "string") field.value = draft[field.name];
    }
    form.addEventListener("input", () => {
      try {
        sessionStorage.setItem(draftKey, JSON.stringify(
          Object.fromEntries(fields.map(field => [field.name, field.value]))
        ));
      } catch {
        // The form remains usable if browser storage is full or disabled.
      }
    });
  } catch {
    // The form remains usable without browser storage.
  }

  for (const button of form.querySelectorAll("[data-mock-run]")) {
    button.addEventListener("click", async () => {
      const question = button.closest("section");
      const output = question.querySelector("pre");
      const field = question.querySelector("textarea");
      output.hidden = false;
      output.textContent = "正在运行…";
      button.disabled = true;
      try {
        const response = await fetch("/mock/run", {
          method: "POST",
          body: new URLSearchParams({
            token: form.elements.token.value,
            round: form.dataset.mockRound,
            id: button.dataset.mockRun,
            code: field.value,
          }),
        });
        if (!response.ok) throw new Error();
        output.textContent = await response.text();
      } catch {
        output.textContent = "运行失败，请检查代码长度后重试。";
      } finally {
        button.disabled = false;
      }
    });
  }
}
