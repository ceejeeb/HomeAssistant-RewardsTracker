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
    const personId = state?.attributes?.person || "";
    const person = personId ? hass.states[personId] : null;
    const personKey = person
      ? `${person.attributes?.friendly_name || ""}|${person.attributes?.entity_picture || ""}`
      : "";
    const key = state
      ? `${state.last_updated}|${JSON.stringify(state.attributes)}|${personKey}|${this._error}`
      : `missing|${this._error}`;
    if (key === this._key && this.shadowRoot.childElementCount) {
      return;
    }
    this._key = key;
    this._render();
  }

  getCardSize() {
    return 10;
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

    const personId = attr.person || "";
    const person = personId ? this._hass.states[personId] : null;
    const picture = person?.attributes?.entity_picture || "";
    const displayName = person?.attributes?.friendly_name || attr.child_name;
    const initial = escapeHtml((displayName || "?").trim().charAt(0).toUpperCase() || "?");
    const avatar = picture
      ? `<img class="avatar" src="${escapeHtml(picture)}" alt="">`
      : `<div class="avatar fallback" aria-hidden="true">${initial}</div>`;
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
    const shop = rewards
      .map((reward) => {
        const cost = Number(reward.cost);
        return this._buy({
          action: "spend",
          rewardId: reward.id,
          icon: reward.icon,
          name: reward.description,
          price: formatAmount(symbol, cost),
          disabled: balance < cost,
        });
      })
      .join("");

    this.shadowRoot.innerHTML = this._shell(`
      <div class="hero">
        ${avatar}
        <div class="hero-copy">
          <div class="hero-name">${escapeHtml(displayName)}</div>
          <button class="award" data-action="award_tick">
            <ha-icon icon="${escapeHtml(safeIcon(tier1Icon))}"></ha-icon>
            <span>${escapeHtml(tier1Name)}</span>
          </button>
        </div>
      </div>
      ${error}
      ${this._icons(tier1Name, tier1Icon, ticks, tier1Count, "ticks")}
      ${this._swoosh("to-stars")}
      ${this._icons(tier2Name, tier2Icon, stars, tier2Count, "stars")}
      ${this._swoosh("to-bank")}
      <div class="bank">
        <div class="roof" aria-hidden="true"></div>
        <div class="vault">
          <div class="columns" aria-hidden="true"><span></span><span></span><span></span></div>
          <div class="vault-label">Bank</div>
          <div class="vault-amount">${escapeHtml(formatAmount(symbol, balance))}</div>
        </div>
      </div>
      <div class="shop">
        ${shop}
        ${this._buy({
          action: "deposit",
          icon: "mdi:plus",
          name: "Save",
          price: `+${unit}`,
          disabled: balance < 1,
        })}
        ${this._buy({
          action: "withdraw",
          icon: "mdi:minus",
          name: "Take out",
          price: `-${unit}`,
          disabled: savings < 1,
        })}
      </div>
      <div class="savings-box">
        <div class="vault jar">
          <div class="vault-label">Savings</div>
          <div class="vault-amount">${escapeHtml(formatAmount(symbol, savings))}</div>
          ${this._meter(interest, 100)}
        </div>
      </div>
    `);
  }

  _icons(label, icon, earned, total, align) {
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
    return `
      <div class="icon-row ${align}" role="img" aria-label="${escapeHtml(label)} ${have} of ${shown}">
        ${tokens.join("")}
      </div>
    `;
  }

  _swoosh(kind) {
    const path =
      kind === "to-stars"
        ? `<path d="M36 18 C 110 6, 170 50, 248 32" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>
           <path d="M230 18 L256 34 L226 44" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>`
        : `<path d="M246 10 C 250 38, 194 58, 160 58" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>
           <path d="M176 44 L156 66 L146 42" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>`;
    return `<svg class="swoosh ${kind}" viewBox="0 0 320 70" aria-hidden="true">${path}</svg>`;
  }

  _buy({ action, rewardId, icon, name, price, disabled }) {
    const rewardAttr = rewardId ? ` data-reward-id="${escapeHtml(rewardId)}"` : "";
    return `
      <button class="buy" data-action="${action}"${rewardAttr} aria-label="${escapeHtml(name)} ${escapeHtml(price)}" ${disabled ? "disabled" : ""}>
        <ha-icon icon="${escapeHtml(safeIcon(icon))}"></ha-icon>
        <span class="buy-name">${escapeHtml(name)}</span>
        <span class="buy-cost">${escapeHtml(price)}</span>
      </button>
    `;
  }

  _meter(value, total) {
    const width = barWidth(value, total);
    return `
      <div class="track" role="meter" aria-label="Interest" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${Number(value) || 0}">
        <div class="fill" style="width: ${width}%"></div>
      </div>
    `;
  }

  _shell(body) {
    return `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .hero {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 18px;
        }
        .avatar {
          width: 92px;
          height: 92px;
          border-radius: 50%;
          object-fit: cover;
          flex: 0 0 92px;
          background: var(--secondary-background-color, rgba(0, 0, 0, 0.06));
        }
        .avatar.fallback {
          display: grid;
          place-items: center;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font-size: 42px;
          font-weight: 700;
        }
        .hero-copy { min-width: 0; }
        .hero-name {
          font-size: 28px;
          font-weight: 800;
          line-height: 1.1;
          margin-bottom: 8px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .award {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          border: none;
          border-radius: 999px;
          padding: 10px 18px 10px 12px;
          background: var(--primary-color);
          color: var(--text-primary-color, #fff);
          font: inherit;
          font-size: 18px;
          font-weight: 800;
          cursor: pointer;
        }
        .award ha-icon {
          --mdc-icon-size: 28px;
          color: var(--text-primary-color, #fff);
        }
        .icon-row {
          display: flex;
          flex-wrap: wrap;
          gap: 2px;
          width: 75%;
        }
        .icon-row.ticks { justify-content: flex-start; }
        .icon-row.stars {
          justify-content: flex-end;
          margin-left: auto;
        }
        .token {
          width: 48px;
          height: 48px;
          display: grid;
          place-items: center;
        }
        .token ha-icon { --mdc-icon-size: 44px; }
        .token.earned ha-icon { color: var(--primary-color); }
        .token.waiting ha-icon {
          color: var(--primary-text-color);
          opacity: 0.22;
        }
        .swoosh {
          display: block;
          width: 82%;
          height: 46px;
          margin: 2px 0;
          color: var(--primary-color);
        }
        .swoosh.to-stars { margin-left: 2%; }
        .swoosh.to-bank { margin-left: auto; margin-right: 2%; }
        .roof {
          width: 0;
          height: 0;
          margin: 8px auto 0;
          border-left: 46px solid transparent;
          border-right: 46px solid transparent;
          border-bottom: 20px solid var(--primary-color);
        }
        .vault {
          width: 74%;
          margin: 0 auto;
          text-align: center;
          border: 3px solid var(--primary-color);
          border-radius: 4px 4px 22px 22px;
          padding: 8px 12px 16px;
          background: color-mix(in srgb, var(--primary-color) 14%, transparent);
        }
        .columns {
          display: flex;
          justify-content: space-between;
          width: 70%;
          margin: 0 auto 6px;
        }
        .columns span {
          width: 8px;
          height: 16px;
          border-radius: 2px;
          background: var(--primary-color);
        }
        .vault.jar {
          border-radius: 32px;
          margin-top: 18px;
          padding-top: 14px;
          padding-bottom: 16px;
        }
        .vault-label {
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--secondary-text-color);
        }
        .vault-amount {
          font-size: 40px;
          font-weight: 800;
          line-height: 1.1;
        }
        .track {
          height: 16px;
          margin-top: 12px;
          border-radius: 99px;
          background: var(--divider-color);
          overflow: hidden;
        }
        .fill {
          height: 100%;
          border-radius: 99px;
          background: var(--primary-color);
        }
        .shop {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-top: 16px;
        }
        .buy {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 4px;
          min-height: 108px;
          padding: 10px 6px;
          border: none;
          border-radius: 18px;
          background: var(--secondary-background-color, rgba(0, 0, 0, 0.06));
          color: var(--primary-text-color);
          font: inherit;
          text-align: center;
          cursor: pointer;
        }
        .buy ha-icon { --mdc-icon-size: 34px; }
        .buy-name {
          font-size: 13px;
          font-weight: 700;
          line-height: 1.15;
          max-height: 2.3em;
          overflow: hidden;
        }
        .buy-cost { font-size: 16px; font-weight: 800; }
        .buy[disabled] {
          opacity: 0.4;
          cursor: default;
        }
        ha-icon { color: var(--primary-color); }
        .empty, .error { margin: 0; }
        .error { color: var(--error-color, #db4437); margin: -8px 0 12px; }
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
