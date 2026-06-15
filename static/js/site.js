document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#prediction-form");
  if (!form) return;

  const teamA = form.querySelector('select[name="teamA"]');
  const teamB = form.querySelector('select[name="teamB"]');
  const stage = form.querySelector('select[name="stage"]');
  const fixtureId = form.querySelector('input[name="fixtureId"]');

  document.querySelectorAll("[data-prefill-team-a]").forEach((button) => {
    button.addEventListener("click", () => {
      teamA.value = button.dataset.prefillTeamA;
      teamB.value = button.dataset.prefillTeamB;
      stage.value = button.dataset.prefillStage;
      fixtureId.value = button.dataset.prefillFixtureId || "";
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  const swapButton = document.querySelector("[data-swap-teams]");
  if (swapButton) {
    swapButton.addEventListener("click", () => {
      const next = teamA.value;
      teamA.value = teamB.value;
      teamB.value = next;
      fixtureId.value = "";
    });
  }

  form.addEventListener("change", (event) => {
    if (event.target.matches('select[name="teamA"], select[name="teamB"], select[name="stage"]')) {
      fixtureId.value = "";
    }
  });

  const groupButtons = document.querySelectorAll("[data-group-filter]");
  const groupCards = document.querySelectorAll("[data-group-bucket]");
  const groupSwitches = document.querySelectorAll("[data-group-switch]");
  const groupPanels = document.querySelectorAll("[data-group-panel]");
  let currentGroupMode = "focus";

  const activateGroup = (groupName) => {
    groupSwitches.forEach((pill) => {
      pill.classList.toggle("is-active", pill.dataset.groupSwitch === groupName);
    });
    groupPanels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.groupPanel === groupName);
    });
  };

  const applyGroupMode = (mode) => {
    currentGroupMode = mode;
    groupButtons.forEach((item) => item.classList.toggle("is-active", item.dataset.groupFilter === mode));
    groupCards.forEach((card) => {
      const bucket = card.dataset.groupBucket;
      card.hidden = mode === "focus" && bucket !== "focus";
      card.classList.toggle("group-card--compact-mode", mode === "compact");
    });
    groupSwitches.forEach((pill) => {
      const bucket = pill.dataset.groupBucket;
      pill.hidden = mode === "focus" && bucket !== "focus";
      pill.classList.toggle("group-pill--compact", mode === "compact");
    });
    if (mode === "compact") {
      groupPanels.forEach((panel) => {
        panel.hidden = true;
      });
    } else {
      const visibleSwitches = Array.from(groupSwitches).filter((pill) => !pill.hidden);
      const activeSwitch = visibleSwitches.find((pill) => pill.classList.contains("is-active")) || visibleSwitches[0];
      if (activeSwitch) {
        activateGroup(activeSwitch.dataset.groupSwitch);
      }
    }
  };

  groupButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const mode = button.dataset.groupFilter;
      applyGroupMode(mode);
    });
  });

  groupSwitches.forEach((pill) => {
    pill.addEventListener("click", () => {
      if (currentGroupMode === "compact") return;
      activateGroup(pill.dataset.groupSwitch);
    });
  });

  applyGroupMode(currentGroupMode);
});
