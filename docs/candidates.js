function renderCandidates(result, target) {
  target.classList.add("reply-comparison");
  target.replaceChildren();
  if (!result.candidates.length) {
    target.textContent = result.reply;
    return;
  }
  const ordered = [...result.candidates].sort((a, b) =>
    Number(b.module === result.module) - Number(a.module === result.module));
  for (const candidate of ordered) {
    const chosen = candidate.module === result.module;
    const card = document.createElement("article");
    card.className = chosen ? "reply-option winner" : "reply-option";
    const header = document.createElement("header");
    const label = document.createElement("strong");
    label.textContent = chosen ? "Chosen" : "Alternative";
    const module = document.createElement("code");
    module.textContent = candidate.module;
    header.append(label, module);
    const reply = document.createElement("p");
    reply.textContent = candidate.reply;
    card.append(header, reply);
    target.append(card);
  }
}
