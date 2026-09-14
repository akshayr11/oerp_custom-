frappe.ui.form.on('Supplier', {
    refresh: function(frm) {
        set_categories_filter(frm);
    }
});

frappe.ui.form.on('Item Categories', {
    categories_add: function(frm, cdt, cdn) {
        set_categories_filter(frm);
    }
});

function set_categories_filter(frm) {
    frm.set_query('categories', 'custom_item_categories', function() {
        return {
            filters: {
                is_group: 0
            }
        };
    });
}