// Home Assistant already bundles the `lit` library so we can import it directly
// without relying on an external CDN.
import { LitElement, html, css } from "lit";

/**
 * Garden Summary Card
 * Displays key sensor values for a list of plants and highlights
 * any that require attention. An alert icon appears when the
 * root zone is depleted above the configured threshold or the
 * environment quality is rated "poor". Plant objects can override
 * the default sensor names with `moisture_entity`, `quality_entity`,
 * and `depletion_entity` keys.
 */
class GardenSummaryCard extends LitElement {
  static properties = {
    hass: {},
    _config: {},
  };

  static styles = css`
    table {
      width: 100%;
      border-spacing: 0;
    }
    th,
    td {
      padding: 4px;
      text-align: left;
    }
    th {
      font-weight: bold;
    }
    tr.priority-high td {
      color: var(--error-color);
      font-weight: bold;
    }
    ha-icon {
      --mdc-icon-size: 20px;
    }
  `;

  setConfig(config) {
    if (!Array.isArray(config.plants)) {
      throw new Error("plants array required");
    }
    this._config = {
      depletion_threshold: 80,
      bad_quality_state: "poor",
      ...config,
    };
  }

  createRenderRoot() {
    // Render into the main DOM so HA themes and fonts apply
    return this;
  }

  getCardSize() {
    return 3;
  }

  render() {
    if (!this.hass || !this._config) {
      return html``;
    }

    const rows = this._config.plants.map((p) => {
      const id = p.id;
      const name = p.name || id;
      const moisture =
        this.hass.states[p.moisture_entity || `sensor.${id}_smoothed_moisture`];
      const quality =
        this.hass.states[p.quality_entity || `sensor.${id}_env_quality`];
      const depletion =
        this.hass.states[p.depletion_entity || `sensor.${id}_depletion`];
      const moistVal = moisture ? moisture.state : "n/a";
      const qualVal = quality ? quality.state : "n/a";
      const depleteVal = depletion ? depletion.state : "n/a";
      const threshold =
        p.depletion_threshold ?? this._config.depletion_threshold;
      const badQuality = String(
        p.bad_quality_state ?? this._config.bad_quality_state
      ).toLowerCase();
      const depletionPct = depletion ? parseFloat(depletion.state) : NaN;
      const isHighPriority =
        (!Number.isNaN(depletionPct) && depletionPct > threshold) ||
        (quality && String(quality.state).toLowerCase() === badQuality);
      const icon = isHighPriority ? "mdi:alert-circle" : "mdi:check-circle";
      const rowClass = isHighPriority ? "priority-high" : "";

      return html`
        <tr class=${rowClass}>
          <td>${name}</td>
          <td>${moistVal}</td>
          <td>${qualVal}</td>
          <td>${depleteVal}</td>
          <td>
            <ha-icon icon="${icon}" title="${isHighPriority ? "Attention" : "OK"}"></ha-icon>
          </td>
        </tr>`;
    });

    return html`
      <ha-card header=${this._config.title || "Garden Summary"}>
        <table class="plants">
          <thead>
            <tr>
              <th>Plant</th>
              <th>Moisture</th>
              <th>Env Quality</th>
              <th>Depletion</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </ha-card>
    `;
  }
}

if (!customElements.get("garden-summary-card")) {
  customElements.define("garden-summary-card", GardenSummaryCard);
}

