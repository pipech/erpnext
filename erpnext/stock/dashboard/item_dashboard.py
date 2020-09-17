from __future__ import unicode_literals

import frappe
from frappe.model.db_query import DatabaseQuery


@frappe.whitelist()
def get_data(
    item_code=None, warehouse=None, item_group=None,
    brand=None, swd_barcode=None,
    start=0, sort_by='actual_qty', sort_order='desc'
):
    '''Return data to render the item dashboard'''

    # get swd pos user and warehouse config
    pos_user_list = frappe.get_all(
        doctype='POS Stock Summary User',
        fields='user',
    )
    pos_user_list = [u.get('user') for u in pos_user_list]
    wh_pos_list = frappe.get_all(
        doctype='POS Stock Summary Warehouse',
        fields='warehouse',
    )
    wh_pos_list = [w.get('warehouse') for w in wh_pos_list]

    current_user = frappe.session.user

    filters = []
    if swd_barcode:
        items = frappe.db.sql_list(
            """
            SELECT
                i.name
            FROM
                `tabItem` i
            WHERE
                i.swd_barcode LIKE '%{swd_barcode}%'
            """.format(swd_barcode=swd_barcode)
        )
        filters.append(['item_code', 'in', items])

    if item_code:
        filters.append(['item_code', 'like', item_code])

    if item_group:
        lft, rgt = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"])
        items = frappe.db.sql_list("""
            select i.name from `tabItem` i
            where exists(select name from `tabItem Group`
                where name=i.item_group and lft >=%s and rgt<=%s)
        """, (lft, rgt))
        filters.append(['item_code', 'in', items])
    if brand:
        if frappe.db.exists('Brand', brand):
            items = frappe.db.sql_list(
                """
                SELECT
                    i.name
                FROM
                    `tabItem` i
                WHERE
                    i.brand = '{brand}'
                """.format(brand=brand)
            )
            filters.append(['item_code', 'in', items])
    if current_user in pos_user_list:
        if warehouse:
            if warehouse in wh_pos_list:
                filters.append(['warehouse', '=', warehouse])
            else:
                return []
        else:
            filters.append(['warehouse', 'in', wh_pos_list])
    else:
        if warehouse:
            filters.append(['warehouse', '=', warehouse])

    try:
        # check if user has any restrictions based on user permissions on warehouse
        if DatabaseQuery('Warehouse', user=frappe.session.user).build_match_conditions():
            filters.append(['warehouse', 'in', [w.name for w in frappe.get_list('Warehouse')]])
    except frappe.PermissionError:
        # user does not have access on warehouse
        return []

    items = frappe.db.get_all(
        'Bin',
        fields=[
            'item_code', 'warehouse', 'projected_qty',
            'reserved_qty', 'reserved_qty_for_production',
            'reserved_qty_for_sub_contract', 'actual_qty',
            'valuation_rate'
        ],
        or_filters={
            'projected_qty': ['!=', 0],
            'reserved_qty': ['!=', 0],
            'reserved_qty_for_production': ['!=', 0],
            'reserved_qty_for_sub_contract': ['!=', 0],
            'actual_qty': ['!=', 0],
        },
        filters=filters,
        order_by=sort_by + ' ' + sort_order,
        limit_start=start,
        limit_page_length='21'
    )

    for item in items:
        item.update({
            'item_name': frappe.get_cached_value("Item", item.item_code, 'item_name'),
            'disable_quick_entry': frappe.get_cached_value("Item", item.item_code, 'has_batch_no')
                or frappe.get_cached_value("Item", item.item_code, 'has_serial_no'),
            'swd_barcode': frappe.get_cached_value('Item', item.item_code, 'swd_barcode'),
        })

    return items
