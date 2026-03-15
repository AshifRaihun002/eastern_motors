/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

class WarrantyOverview extends Component {
    static template = "custom_warranty_claim_management.WarrantyOverview";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ cards: [] });

        onMounted(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        const data = await this.orm.call(
            "warranty.claim",
            "get_overview_data",
            []
        );
        this.state.cards = data;
    }

    getMaxCount(card) {
        return Math.max(card.previous, card.current, 1);
    }

    getBarHeight(count, max) {
        return Math.round((count / max) * 100);
    }

    openList(state, dateFilter) {
        const today = new Date().toISOString().split('T')[0];
        let domain = [['state', '=', state]];

        if (dateFilter === 'previous') {
            domain.push(['warranty_claim_date', '<', today]);
        } else {
            domain.push(['warranty_claim_date', '>=', today]);
        }

        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Warranty Claims',
            res_model: 'warranty.claim',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
        });
    }
}

registry.category("actions").add(
    "custom_warranty_claim_management.warranty_overview",
    WarrantyOverview
);