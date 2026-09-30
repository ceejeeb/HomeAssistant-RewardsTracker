const CARD_TYPE = "rewards-tracker-card";

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatAmount(symbol, amount) {
  const mark = symbol || "";
  if ([...mark].length > 1) {
    return `${mark} ${amount}`;
  }
  return `${mark}${amount}`;
}

function safeIcon(icon) {
  return /^[a-z0-9-]+:[a-z0-9-]+$/i.test(icon || "") ? icon : "mdi:cash";
}

function barWidth(value, total) {
  if (!total || total < 1) {
    return 0;
  }
  return Math.max(0, Math.min(100, (Number(value) / total) * 100));
}

class RewardsTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this.config = null;
    this._key = "";
    this._error = "";
    this.shadowRoot.addEventListener("click", (event) => {
      this._onClick(event);
    });
  }

  static getConfigElement() {
    return document.createElement("rewards-tracker-card-editor");
  }

  static getStubConfig() {
    return { entity: "" };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Rewards Tracker needs a card configuration.");
    }
    this.config = config;
    this._key = "";
    if (this._hass) {
      this._render();
    }
  }

  set hass(hass) {
    this._hass = hass;
    const state = this.config?.entity ? hass.states[this.config.entity] : null;
    const key = state
      ? `${state.last_updated}|${JSON.stringify(state.attributes)}|${this._error}`
      : `missing|${this._error}`;
    if (key === this._key && this.shadowRoot.childElementCount) {
      return;
    }
    this._key = key;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _state() {
    if (!this._hass || !this.config?.entity) {
      return null;
    }
    return this._hass.states[this.config.entity] || null;
  }

  _render() {
    const state = this._state();
    if (!this.config?.entity) {
      this.shadowRoot.innerHTML = this._shell(
        `<p class="empty">Choose the Money sensor for a child.</p>`
      );
      return;
    }
    if (!state) {
      this.shadowRoot.innerHTML = this._shell(
        `<p class="empty">That sensor is unavailable.</p>`
      );
      return;
    }
    const attr = state.attributes || {};
    if (!attr.child_name || attr.balance === undefined) {
      this.shadowRoot.innerHTML = this._shell(
        `<p class="empty">Pick a Rewards Tracker Money sensor.</p>`
      );
      return;
    }

    const symbol = attr.currency_symbol || "";
    const balance = Number(attr.balance);
    const savings = Number(attr.savings);
    const ticks = Number(attr.ticks);
    const stars = Number(attr.stars);
    const interest = Number(attr.interest_pence);
    const tier1Name = attr.tier1_name || "Ticks";
    const tier2Name = attr.tier2_name || "Stars";
    const tier1Icon = attr.tier1_icon || "mdi:check";
    const tier2Icon = attr.tier2_icon || "mdi:star";
    const tier1Count = Number(attr.tier1_count || attr.ticks_per_star) || 1;
    const tier2Count = Number(attr.tier2_count || attr.stars_per_pound) || 1;
    const rewards = Array.isArray(attr.rewards) ? attr.rewards : [];
    const error = this._error
      ? `<p class="error">${escapeHtml(this._error)}</p>`
      : "";

    const unit = formatAmount(symbol, 1);
    const spend = rewards.length
      ? rewards
          .map((reward) => {
            const cost = Number(reward.cost);
            const blocked = balance < cost;
            return `
              <button class="spend" data-action="spend" data-reward-id="${escapeHtml(reward.id)}" ${blocked ? "disabled" : ""}>
                <ha-icon icon="${escapeHtml(safeIcon(reward.icon))}"></ha-icon>
                <span class="spend-name">${escapeHtml(reward.description)}</span>
                <span class="spend-cost">${escapeHtml(formatAmount(symbol, cost))}</span>
              </button>
            `;
          })
          .join("")
      : `<p class="hint">No ways to spend yet. Add them from Configure on the integration.</p>`;

    this.shadowRoot.innerHTML = this._shell(`
      <div class="header">${escapeHtml(attr.child_name)}</div>
      ${error}
      ${this._tier(tier1Name, tier1Icon, ticks, tier1Count, true)}
      ${this._tier(tier2Name, tier2Icon, stars, tier2Count, false)}
      <div class="pot">
        <div class="label">Money</div>
        <div class="value">${escapeHtml(formatAmount(symbol, balance))}</div>
      </div>
      <div class="spend-list">${spend}</div>
      <div class="pot savings">
        <div class="savings-main">
          <div class="label">Savings</div>
          <div class="value">${escapeHtml(formatAmount(symbol, savings))}</div>
        </div>
        <div class="transfers">
          <button class="icon-btn" data-action="deposit" aria-label="Deposit ${escapeHtml(unit)}" ${balance < 1 ? "disabled" : ""}>
            <ha-icon icon="mdi:arrow-down-bold"></ha-icon>
          </button>
          <button class="icon-btn" data-action="withdraw" aria-label="Withdraw ${escapeHtml(unit)}" ${savings < 1 ? "disabled" : ""}>
            <ha-icon icon="mdi:arrow-up-bold"></ha-icon>
          </button>
        </div>
      </div>
      ${this._meter("Interest", interest, 100)}
    `);
  }

  _tier(label, icon, earned, total, award) {
    const safe = escapeHtml(safeIcon(icon));
    const shown = Math.max(1, Math.min(Number(total) || 1, 24));
    const have = Math.max(0, Math.min(Number(earned) || 0, shown));
    const tokens = [];
    for (let index = 0; index < shown; index += 1) {
      const state = index < have ? "earned" : "waiting";
      tokens.push(
        `<span class="token ${state}"><ha-icon icon="${safe}"></ha-icon></span>`
      );
    }
    const action = award
      ? `<button class="icon-btn" data-action="award_tick" aria-label="${escapeHtml(label)}"><ha-icon icon="mdi:plus"></ha-icon></button>`
      : "";
    return `
      <div class="tier">
        <div class="meter-row">
          <span>${escapeHtml(label)}</span>
          ${action}
        </div>
        <div class="icon-row" role="img" aria-label="${escapeHtml(label)} ${have} of ${shown}">
          ${tokens.join("")}
        </div>
      </div>
    `;
  }

  _meter(label, value, total) {
    const width = barWidth(value, total);
    return `
      <div class="meter">
        <div class="meter-row">
          <span>${escapeHtml(label)}</span>
        </div>
        <div class="track" role="meter" aria-label="${escapeHtml(label)}" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${Number(value) || 0}">
          <div class="fill" style="width: ${width}%"></div>
        </div>
      </div>
    `;
  }

  _shell(body) {
    return `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .header {
          font-size: 20px;
          font-weight: 500;
          margin-bottom: 12px;
        }
        .label, .hint {
          color: var(--secondary-text-color);
        }
        .label { font-size: 12px; }
        .value { font-size: 28px; font-weight: 500; line-height: 1.2; }
        .meter, .tier { margin-bottom: 14px; }
        .pot { margin-bottom: 4px; }
        .savings {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-top: 14px;
          margin-bottom: 10px;
        }
        .transfers { display: flex; gap: 8px; }
        .meter-row, .spend {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .meter-row { justify-content: space-between; font-size: 13px; margin-bottom: 6px; }
        .icon-row {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }
        .token {
          width: 32px;
          height: 32px;
          display: grid;
          place-items: center;
        }
        .token ha-icon { --mdc-icon-size: 28px; }
        .token.earned ha-icon { color: var(--primary-color); }
        .token.waiting ha-icon {
          color: var(--primary-text-color);
          opacity: 0.22;
        }
        .track {
          height: 18px;
          border-radius: 99px;
          background: var(--divider-color);
          overflow: hidden;
        }
        .fill {
          height: 100%;
          background: var(--primary-color);
        }
        .icon-btn, .spend {
          font: inherit;
          color: var(--primary-text-color);
          cursor: pointer;
        }
        .icon-btn {
          width: 40px;
          height: 40px;
          border: none;
          border-radius: 12px;
          padding: 0;
          display: grid;
          place-items: center;
          background: var(--secondary-background-color, rgba(0, 0, 0, 0.06));
        }
        .icon-btn ha-icon { --mdc-icon-size: 22px; }
        .icon-btn[disabled], .spend[disabled] {
          opacity: 0.4;
          cursor: default;
        }
        .spend {
          width: 100%;
          text-align: left;
          border: none;
          border-top: 1px solid var(--divider-color);
          background: transparent;
          padding: 10px 0;
        }
        .spend-name { flex: 1; }
        .spend-cost { font-weight: 500; }
        ha-icon { color: var(--primary-color); }
        .empty, .hint, .error { margin: 0; }
        .error { color: var(--error-color, #db4437); margin-top: 8px; }
        .hint { font-size: 13px; padding: 8px 0; }
      </style>
      <ha-card>${body}</ha-card>
    `;
  }

  async _onClick(event) {
    const target = event.target instanceof Element ? event.target : event.target?.parentElement;
    const button = target?.closest?.("button");
    if (!button || button.hasAttribute("disabled") || !this._hass || !this.config?.entity) {
      return;
    }
    const action = button.dataset.action;
    if (!action) {
      return;
    }
    const data = {};
    if (action === "spend") {
      data.reward_id = button.dataset.rewardId;
    }
    try {
      await this._hass.callService("rewards_tracker", action, data, {
        entity_id: this.config.entity,
      });
      if (this._error) {
        this._error = "";
        this._key = "";
        this._render();
      }
    } catch (_err) {
      this._error = "That did not go through.";
      this._key = "";
      this._render();
    }
  }
}

class RewardsTrackerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    if (this._picker && config?.entity) {
      this._picker.value = config.entity;
    }
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || this._picker) {
      if (this._picker) {
        this._picker.hass = this._hass;
      }
      return;
    }
    const picker = document.createElement("ha-entity-picker");
    picker.label = "Money sensor";
    picker.hass = this._hass;
    picker.value = this._config?.entity || "";
    picker.includeDomains = ["sensor"];
    picker.entityFilter = (entity) =>
      entity?.attributes?.role === "balance" && !!entity.attributes.child_name;
    picker.addEventListener("value-changed", (event) => {
      const value = event.detail?.value;
      if (!value || value === this._config?.entity) {
        return;
      }
      this._config = { ...this._config, entity: value };
      picker.value = value;
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config: this._config },
          bubbles: true,
          composed: true,
        })
      );
    });
    this.innerHTML = "";
    this.append(picker);
    this._picker = picker;
  }
}

customElements.define(CARD_TYPE, RewardsTrackerCard);
customElements.define("rewards-tracker-card-editor", RewardsTrackerCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: CARD_TYPE,
  name: "Rewards Tracker",
  description: "Ticks, stars, money, and savings for one child",
  preview: true,
});
