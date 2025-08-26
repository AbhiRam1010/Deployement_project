"""
URL configuration for zomato project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .views import *
urlpatterns = [
    path('masrter_registration',masrter_registration,name='masrter_registration'),
    path('add_item',add_item,name="add_item"),
    path('master_login',master_login,name='master_login'),
    path('user_logout', user_logout, name='user_logout'),
    path('menu',menu,name='menu'),
    path('delete<pk>',delete,name='delete'),
    path('update<pk>',update,name="update"),
    

]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare
import logging
import re

_logger = logging.getLogger(__name__)

class MassDeliveryPickupWizard(models.TransientModel):
    _name = 'mass.delivery.pickup.wizard'
    _description = 'Mass Delivery Pickup Wizard'

    picking_id = fields.Many2one(
        'stock.picking', string="Delivery Order", readonly=True, required=True)
    sale_order_id = fields.Many2one(
        'sale.order', string="Sale Order", readonly=True, related='picking_id.sale_id')
    partner_id = fields.Many2one(
        'res.partner', string="Customer", readonly=True, related='picking_id.partner_id')
    move_line_ids = fields.One2many(
        'mass.delivery.pickup.wizard.move', 'wizard_id', string="Products to Deliver")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get('active_id')
        if not picking_id:
            raise UserError(_("No active delivery order found."))

        picking = self.env['stock.picking'].browse(picking_id)
        if not picking.sale_id:
            raise UserError(_("The delivery order '%s' is not linked to a sales order.") % picking.name)
        if not picking.partner_id.x_default_dc_location_id:
            raise UserError(
                _("The customer '%s' does not have a Default DC Location set.") % picking.partner_id.name)

        location_mappings = {
            'loc1': ['DCG Farm/DCGF A Bin', 'DCD Farm/DCDF A Bin'],
            'loc2': ['DCG Farm/DCGF B Bin', 'DCD Farm/DCDF B Bin'],
            'loc3': ['DCG Farm/DCGF UG Bin', 'DCD Farm/DCDF UG Bin'],
            'loc4': ['DCG Purchase/DCGP A Bin', 'DCD Purchase/DCDP A Bin'],
            'loc5': ['DCG Purchase/DCGP B Bin', 'DCD Purchase/DCDP B Bin'],
            'loc6': ['DCG Purchase/DCGP UG Bin', 'DCD Purchase/DCDP UG Bin'],
            'loc7': ['DCG Purchase/DCGP B+ Bin', 'DCD Purchase/DCDP B+ Bin'],
            'loc8': ['DCG Farm/DCGF B+ Bin', 'DCD Farm/DCDF B+ Bin'],
        }

        all_locations_data = []
        for loc_list in location_mappings.values():
            all_locations_data.extend(loc_list)
        all_locations = self.env['stock.location'].search([('complete_name', 'in', all_locations_data)])

        move_lines_vals = []
        for line in picking.sale_id.order_line:
            product = line.product_id
            if not product or not product.id:
                _logger.warning("Skipping sale order line with missing product: %s", line)
                continue

            category = product.categ_id.name if product.categ_id else ''
            if category == 'B2B-Dry':
                relevant_locations = all_locations.filtered(lambda loc: loc.complete_name in [location_mappings[f'loc{i}'][1] for i in range(1, 9)])
            elif category == 'B2B-Green':
                relevant_locations = all_locations.filtered(lambda loc: loc.complete_name in [location_mappings[f'loc{i}'][0] for i in range(1, 9)])
            else:
                relevant_locations = self.env['stock.location']
                _logger.warning("Product %s has unsupported category: %s", product.display_name, category)
                continue

            quant_domain = [
                ('product_id', '=', product.id),
                ('location_id', 'in', relevant_locations.ids),
                ('quantity', '>', 0)
            ]
            available_quants = self.env['stock.quant'].search(quant_domain)

            location_data = {loc.complete_name: {'on_hand': 0.0, 'picked': 0.0} for loc in relevant_locations}
            for quant in available_quants:
                location_data[quant.location_id.complete_name]['on_hand'] = quant.quantity

            move = picking.move_ids.filtered(
                lambda m: m.product_id.id == product.id and m.state not in ('done', 'cancel'))[:1]
            if not move:
                _logger.warning("No active stock move found for product: %s. Skipping.", product.display_name)
                continue

            move_line_vals = {
                'move_id': move.id,
                'product_id': product.id,
                'demand_qty_so': line.product_uom_qty or 0.0,
                'demand_uom_id': line.product_uom.id,
                'stock_uom_id': product.uom_id.id,
                'picked_qty_so': move.x_commercial_qty_done or 0.0,
                'has_farm_qty': any(location_data[loc.complete_name]['on_hand'] > 0 for loc in relevant_locations
                                    if loc.complete_name in [location_mappings['loc1'][0 if category == 'B2B-Green' else 1],
                                                            location_mappings['loc2'][0 if category == 'B2B-Green' else 1],
                                                            location_mappings['loc3'][0 if category == 'B2B-Green' else 1],
                                                            location_mappings['loc8'][0 if category == 'B2B-Green' else 1]]),
                'has_b_plus_qty': product.name == 'Potato' and any(location_data[loc.complete_name]['on_hand'] > 0
                                                                  for loc in relevant_locations
                                                                  if loc.complete_name in [location_mappings['loc7'][0 if category == 'B2B-Green' else 1],
                                                                                           location_mappings['loc8'][0 if category == 'B2B-Green' else 1]]),
            }

            # Assign fixed locations based on product category
            for i in range(1, 9):
                loc_key = f'loc{i}'
                loc_name = location_mappings[loc_key][0 if category == 'B2B-Green' else 1]
                loc = all_locations.filtered(lambda l: l.complete_name == loc_name)
                move_line_vals.update({
                    f'loc{i}_id': loc.id if loc else False,
                    f'loc{i}_on_hand_qty': location_data[loc_name]['on_hand'] if loc else 0.0,
                    f'loc{i}_picked_qty': 0.0,
                })

            # Load existing picked quantities from stock.move.line
            existing_move_lines = move.move_line_ids
            for existing_ml in existing_move_lines:
                for i in range(1, 9):
                    loc_id = move_line_vals[f'loc{i}_id']
                    if loc_id and loc_id == existing_ml.location_id.id:
                        move_line_vals[f'loc{i}_picked_qty'] += existing_ml.qty_done

            # Override picked_qty_so if demand_uom_id is 12 (kg)
            total_picked_qty_stock = sum(move_line_vals.get(f'loc{i}_picked_qty', 0.0) for i in range(1, 9))
            if move_line_vals.get('demand_uom_id') == 12:
                move_line_vals['picked_qty_so'] = total_picked_qty_stock

            if not move_line_vals.get('product_id'):
                _logger.error("Product ID missing for move_line_vals: %s", move_line_vals)
                continue

            move_lines_vals.append((0, 0, move_line_vals))
            _logger.info("Prepared move_line_vals: %s", move_line_vals)

        res.update({
            'picking_id': picking.id,
            'move_line_ids': move_lines_vals
        })
        return res

    def action_confirm_pickup(self):
        self.ensure_one()
        picking = self.picking_id
        if picking.state in ('done', 'cancel'):
            raise ValidationError(_("You cannot modify a delivery that is already done or cancelled."))

        for move_line in self.move_line_ids:
            if not move_line.product_id:
                raise ValidationError(_("Product is missing for move line."))
            if not move_line.move_id:
                raise ValidationError(_("No move_id found."))

        # Check if any quantities were picked in this session
        total_all_picked = sum(
            sum(getattr(move_line, f'loc{i}_picked_qty') or 0.0 for i in range(1, 9))
            for move_line in self.move_line_ids
        )
        # if total_all_picked <= 0:
        #     raise ValidationError(_("No quantities were picked. Please specify quantities to deliver before confirming."))

        # Fetch dpw records for all products in move lines
        dpw_records = self.env['distinct.product.piece.weight'].search([
            ('dpw_product_id', 'in', self.move_line_ids.mapped('product_id').ids)
        ])
        dpw_map = {record.dpw_product_id.id: record for record in dpw_records}

        for move_line in self.move_line_ids:
            move = move_line.move_id
            product = move_line.product_id
            stock_uom = move_line.stock_uom_id
            demand_uom = move_line.demand_uom_id
            if not product or not product.id:
                _logger.error("No product associated with move line: %s", move_line)
                continue

            # Ensure stock_uom has a valid rounding value
            stock_uom_rounding = stock_uom.rounding if stock_uom and stock_uom.rounding > 0 else 0.001
            if not stock_uom or stock_uom.rounding <= 0:
                _logger.warning("Invalid rounding for UoM %s (product: %s). Using default rounding 0.001.",
                                stock_uom.name if stock_uom else 'None', product.display_name)

            # Get wizard quantities
            wizard_quantities = {f'loc{i}_id': getattr(move_line, f'loc{i}_picked_qty') or 0.0 for i in range(1, 9)}
            total_picked_qty_stock = sum(wizard_quantities[f'loc{i}_id'] for i in range(1, 9))

            # Get existing move line quantities
            existing_move_lines = move.move_line_ids
            existing_quantities = {}
            for existing_ml in existing_move_lines:
                loc_id = existing_ml.location_id.id
                existing_quantities[loc_id] = existing_quantities.get(loc_id, 0.0) + existing_ml.qty_done

            # Check if quantities have changed
            quantities_changed = False
            for i in range(1, 9):
                loc_id = getattr(move_line, f'loc{i}_id')
                wizard_qty = wizard_quantities[f'loc{i}_id']
                existing_qty = existing_quantities.get(loc_id.id, 0.0) if loc_id else 0.0
                if loc_id and float_compare(wizard_qty, existing_qty, precision_rounding=stock_uom_rounding) != 0:
                    quantities_changed = True
                    _logger.info("Quantity changed for product %s at location %s: wizard=%s, existing=%s",
                                 product.display_name, loc_id.display_name, wizard_qty, existing_qty)

            # Skip if no quantities were picked and no changes were made
            if total_picked_qty_stock <= 0 or not quantities_changed:
                _logger.info("No quantities picked or changed for product %s in this session. Preserving existing move lines.", product.display_name)
                continue

            if not move_line.is_same_uom and move_line.picked_qty_so <= 0:
                raise ValidationError(_(
                    "For product %s, since you have picked a physical quantity, "
                    "you must also enter a commercial 'Quantity to Deliver' greater than zero."
                ) % product.display_name)

            # UoM conversion logic
            is_converted_to_KG = False
            picked_qty_so = move_line.picked_qty_so
            if demand_uom and not move_line.is_same_uom:
                uom_name = demand_uom.name
                match_gm = re.match(r'PCKT-(\d+)GM$', uom_name)
                match_kg = re.match(r'PCKT-(\d+)KG$', uom_name)
                if match_gm:
                    grams = int(match_gm.group(1))
                    picked_qty_so = total_picked_qty_stock * 1000 / grams  # Convert grams to kilograms
                    is_converted_to_KG = True
                elif match_kg:
                    kgrams = int(match_kg.group(1))
                    picked_qty_so = total_picked_qty_stock / kgrams
                    is_converted_to_KG = True

                # Apply dpw conversion if applicable
                dpw_record = dpw_map.get(product.id)
                if not is_converted_to_KG and dpw_record and demand_uom.id == dpw_record.dpw_uom_id.id:
                    total_pieces = total_picked_qty_stock * dpw_record.dpw_no_of_pieces_per_unit
                    picked_qty_so = total_pieces * dpw_record.dpw_weight_per_piece
                    is_converted_to_KG = True

            # Update picked_qty_so in move_line
            move_line.write({'picked_qty_so': picked_qty_so})

            # Create new move line commands with updated quantities
            move_line_commands = []
            for i in range(1, 9):
                loc_id = getattr(move_line, f'loc{i}_id')
                wizard_qty = wizard_quantities[f'loc{i}_id']
                if loc_id and wizard_qty > 0:
                    move_line_commands.append((0, 0, {
                        'picking_id': picking.id,
                        'location_id': loc_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'qty_done': wizard_qty,
                        'product_id': product.id,
                        'product_uom_id': product.uom_id.id,
                    }))
                    _logger.info(f"Added/updated move line: picking_id={picking.id}, location_id={loc_id.id}, qty_done={wizard_qty}")

            if move_line_commands:
                # Delete existing move lines for this move and recreate with updated quantities
                move.move_line_ids.unlink()
                move.write({
                    'move_line_ids': move_line_commands,
                    'x_commercial_qty_done': picked_qty_so,
                    'x_target_qty_stock': total_picked_qty_stock,
                })
                _logger.info("Updated move %s with move lines: %s", move.id, move_line_commands)
            else:
                _logger.warning("No move lines created for move %s.", move.id)
                continue

            if not move_line.is_same_uom and picked_qty_so > 0:
                estimated_total_demand = (total_picked_qty_stock / picked_qty_so) * move.sale_line_id.product_uom_qty
                move.write({'product_uom_qty': estimated_total_demand})
            elif move_line.is_same_uom:
                if float_compare(move.sale_line_id.product_uom_qty, move.product_uom_qty,
                                precision_rounding=stock_uom_rounding) != 0:
                    move.write({'product_uom_qty': move.sale_line_id.product_uom_qty})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }

    def action_open_farm_wizard(self, move_line_id):
        _logger.warning(f"FARM @@@@@@@@@@@")
        move_line = self.env['mass.delivery.pickup.wizard.move'].browse(move_line_id)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mass.delivery.pickup.wizard.farm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'wizard_id': self.id,
                'move_line_id': move_line_id,
                'product_id': move_line.product_id.id,
                'loc1_id': move_line.loc1_id.id,
                'loc1_on_hand_qty': move_line.loc1_on_hand_qty,
                'loc1_picked_qty': move_line.loc1_picked_qty,
                'loc2_id': move_line.loc2_id.id,
                'loc2_on_hand_qty': move_line.loc2_on_hand_qty,
                'loc2_picked_qty': move_line.loc2_picked_qty,
                'loc3_id': move_line.loc3_id.id,
                'loc3_on_hand_qty': move_line.loc3_on_hand_qty,
                'loc3_picked_qty': move_line.loc3_picked_qty,
                'loc8_id': move_line.loc8_id.id if move_line.product_id.name == 'Potato' else False,
                'loc8_on_hand_qty': move_line.loc8_on_hand_qty if move_line.product_id.name == 'Potato' else 0.0,
                'loc8_picked_qty': move_line.loc8_picked_qty if move_line.product_id.name == 'Potato' else 0.0,
            },
        }

    def action_open_b_plus_wizard(self, move_line_id):
        move_line = self.env['mass.delivery.pickup.wizard.move'].browse(move_line_id)
        _logger.warning(f"B++++++++++++++++++++++ @@@@@@@@@@@")
        if move_line.product_id.name != 'Potato':
            raise UserError(_("B+ locations are only available for Potato products."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mass.delivery.pickup.wizard.b_plus',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'wizard_id': self.id,
                'move_line_id': move_line_id,
                'product_id': move_line.product_id.id,
                'loc7_id': move_line.loc7_id.id,
                'loc7_on_hand_qty': move_line.loc7_on_hand_qty,
                'loc7_picked_qty': move_line.loc7_picked_qty,
                'loc8_id': move_line.loc8_id.id,
                'loc8_on_hand_qty': move_line.loc8_on_hand_qty,
                'loc8_picked_qty': move_line.loc8_picked_qty,
            },
        }

class MassDeliveryPickupWizardMove(models.TransientModel):
    _name = 'mass.delivery.pickup.wizard.move'
    _description = 'Mass Delivery Pickup Wizard - Move Line'

    wizard_id = fields.Many2one(
        'mass.delivery.pickup.wizard', required=True, ondelete='cascade')
    move_id = fields.Many2one('stock.move', string="Source Move")
    product_id = fields.Many2one('product.product', string="Product", required=True)
    demand_qty_so = fields.Float(string="Ordered Quantity")
    demand_uom_id = fields.Many2one('uom.uom', string="Ordered UoM")
    stock_uom_id = fields.Many2one('uom.uom', string="Stock UoM")
    is_same_uom = fields.Boolean(compute='_compute_is_same_uom')
    
    total_picked_qty_stock = fields.Float(
        string="Total Quantity Picked", compute='_compute_total_picked_qty_stock', readonly=True)
    picked_qty_so = fields.Float(string="Quantity to Deliver (SO UOM)")
    has_farm_qty = fields.Boolean(string="Has Farm Quantity", default=False)
    has_b_plus_qty = fields.Boolean(string="Has B+ Quantity", default=False)

    loc1_id = fields.Many2one('stock.location', string="Location A")
    loc1_on_hand_qty = fields.Float(string="A Available (kg)", readonly=True)
    loc1_picked_qty = fields.Float(string="A Pick Up (kg)", default=0.0)
    loc2_id = fields.Many2one('stock.location', string="Location B")
    loc2_on_hand_qty = fields.Float(string="B Available (kg)", readonly=True)
    loc2_picked_qty = fields.Float(string="B Pick Up (kg)", default=0.0)
    loc3_id = fields.Many2one('stock.location', string="Location UG")
    loc3_on_hand_qty = fields.Float(string="UG Available (kg)", readonly=True)
    loc3_picked_qty = fields.Float(string="UG Pick Up (kg)", default=0.0)
    loc4_id = fields.Many2one('stock.location', string="Location Purchase A")
    loc4_on_hand_qty = fields.Float(string="Purchase A Available (kg)", readonly=True)
    loc4_picked_qty = fields.Float(string="Purchase A Pick Up (kg)", default=0.0)
    loc5_id = fields.Many2one('stock.location', string="Location Purchase B")
    loc5_on_hand_qty = fields.Float(string="Purchase B Available (kg)", readonly=True)
    loc5_picked_qty = fields.Float(string="Purchase B Pick Up (kg)", default=0.0)
    loc6_id = fields.Many2one('stock.location', string="Location Purchase UG")
    loc6_on_hand_qty = fields.Float(string="Purchase UG Available (kg)", readonly=True)
    loc6_picked_qty = fields.Float(string="Purchase UG Pick Up (kg)", default=0.0)
    loc7_id = fields.Many2one('stock.location', string="Location Purchase B+")
    loc7_on_hand_qty = fields.Float(string="Purchase B+ Available (kg)", readonly=True)
    loc7_picked_qty = fields.Float(string="Purchase B+ Pick Up (kg)", default=0.0)
    loc8_id = fields.Many2one('stock.location', string="Location Farm B+")
    loc8_on_hand_qty = fields.Float(string="Farm B+ Available (kg)", readonly=True)
    loc8_picked_qty = fields.Float(string="Farm B+ Pick Up (kg)", default=0.0)

    @api.depends('demand_uom_id', 'stock_uom_id')
    def _compute_is_same_uom(self):
        for rec in self:
            rec.is_same_uom = (rec.demand_uom_id.id == rec.stock_uom_id.id)

    @api.depends('loc1_picked_qty', 'loc2_picked_qty', 'loc3_picked_qty', 'loc4_picked_qty',
                 'loc5_picked_qty', 'loc6_picked_qty', 'loc7_picked_qty', 'loc8_picked_qty')
    def _compute_total_picked_qty_stock(self):
        for rec in self:
            rec.total_picked_qty_stock = sum(getattr(rec, f'loc{i}_picked_qty') or 0.0 for i in range(1, 9))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'demand_uom_id' in res and res['demand_uom_id'] == 12:
            total_picked_qty_stock = sum(res.get(f'loc{i}_picked_qty', 0.0) for i in range(1, 9))
            res['picked_qty_so'] = total_picked_qty_stock
        else:
            # Apply UoM conversion logic if not kg
            product_id = res.get('product_id')
            demand_uom_id = res.get('demand_uom_id')
            total_picked_qty_stock = sum(res.get(f'loc{i}_picked_qty', 0.0) for i in range(1, 9))
            if product_id and demand_uom_id and total_picked_qty_stock > 0:
                product = self.env['product.product'].browse(product_id)
                demand_uom = self.env['uom.uom'].browse(demand_uom_id)
                is_converted_to_KG = False
                picked_qty_so = total_picked_qty_stock
                uom_name = demand_uom.name
                match_gm = re.match(r'PCKT-(\d+)GM$', uom_name)
                match_kg = re.match(r'PCKT-(\d+)KG$', uom_name)
                if match_gm:
                    grams = int(match_gm.group(1))
                    picked_qty_so = total_picked_qty_stock * 1000 / grams
                    is_converted_to_KG = True
                elif match_kg:
                    kgrams = int(match_kg.group(1))
                    picked_qty_so = total_picked_qty_stock / kgrams
                    is_converted_to_KG = True

                # Apply dpw conversion
                dpw_records = self.env['distinct.product.piece.weight'].search([
                    ('dpw_product_id', '=', product_id)
                ])
                dpw_record = dpw_records[0] if dpw_records else False
                if not is_converted_to_KG and dpw_record and demand_uom_id == dpw_record.dpw_uom_id.id:
                    total_pieces = total_picked_qty_stock * dpw_record.dpw_no_of_pieces_per_unit
                    picked_qty_so = total_pieces * dpw_record.dpw_weight_per_piece
                    is_converted_to_KG = True

                res['picked_qty_so'] = picked_qty_so
        return res

    @api.onchange('loc1_picked_qty', 'loc2_picked_qty', 'loc3_picked_qty', 'loc4_picked_qty',
                  'loc5_picked_qty', 'loc6_picked_qty', 'loc7_picked_qty', 'loc8_picked_qty')
    def _onchange_picked_quantities(self):
        if self._origin.id:
            if not self.product_id:
                self.product_id = self._origin.product_id
            if not self.move_id:
                self.move_id = self._origin.move_id
            if not self.demand_qty_so:
                self.demand_qty_so = self._origin.demand_qty_so
            if not self.demand_uom_id:
                self.demand_uom_id = self._origin.demand_uom_id
            if not self.stock_uom_id:
                self.stock_uom_id = self._origin.stock_uom_id
        for i in range(1, 9):
            loc_id = getattr(self, f'loc{i}_id')
            picked_qty = getattr(self, f'loc{i}_picked_qty')
            on_hand_qty = getattr(self, f'loc{i}_on_hand_qty')
            if loc_id and picked_qty and picked_qty > on_hand_qty:
                raise ValidationError(
                    _("Picked quantity (%s) for location %s cannot exceed available quantity (%s).") %
                    (picked_qty, loc_id.display_name, on_hand_qty))

        # Update picked_qty_so with conversion logic
        is_converted_to_KG = False
        total_picked_qty_stock = self.total_picked_qty_stock
        picked_qty_so = total_picked_qty_stock
        if self.demand_uom_id and not self.is_same_uom:
            uom_name = self.demand_uom_id.name
            match_gm = re.match(r'PCKT-(\d+)GM$', uom_name)
            match_kg = re.match(r'PCKT-(\d+)KG$', uom_name)
            if match_gm:
                grams = int(match_gm.group(1))
                picked_qty_so = total_picked_qty_stock * 1000 / grams
                is_converted_to_KG = True
            elif match_kg:
                kgrams = int(match_kg.group(1))
                picked_qty_so = total_picked_qty_stock / kgrams
                is_converted_to_KG = True

            # Apply dpw conversion
            dpw_records = self.env['distinct.product.piece.weight'].search([
                ('dpw_product_id', '=', self.product_id.id)
            ])
            dpw_record = dpw_records[0] if dpw_records else False
            if not is_converted_to_KG and dpw_record and self.demand_uom_id.id == dpw_record.dpw_uom_id.id:
                total_pieces = total_picked_qty_stock * dpw_record.dpw_no_of_pieces_per_unit
                picked_qty_so = total_pieces * dpw_record.dpw_weight_per_piece
                is_converted_to_KG = True

        if self.demand_uom_id.id == 12:
            picked_qty_so = total_picked_qty_stock
        self.picked_qty_so = picked_qty_so

    def _compute_has_b_plus_qty(self):
        for line in self:
            line.has_b_plus_qty = any([
                line.loc7_on_hand_qty > 0,
                line.loc8_on_hand_qty > 0
            ]) if line.product_id.name == 'Potato' else False

    def _compute_has_farm_qty(self):
        for line in self:
            line.has_farm_qty = any([
                line.loc1_on_hand_qty > 0,
                line.loc2_on_hand_qty > 0,
                line.loc3_on_hand_qty > 0,
                line.loc8_on_hand_qty > 0
            ])

    def open_farm_wizard(self):
        self.ensure_one()
        return {
            'name': 'Farm Pickup',
            'type': 'ir.actions.act_window',
            'res_model': 'mass.delivery.pickup.wizard.farm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'wizard_id': self.wizard_id.id,
                'move_line_id': self.id,
                'product_id': self.product_id.id,
                'loc1_id': self.loc1_id.id,
                'loc1_on_hand_qty': self.loc1_on_hand_qty,
                'loc1_picked_qty': self.loc1_picked_qty,
                'loc2_id': self.loc2_id.id,
                'loc2_on_hand_qty': self.loc2_on_hand_qty,
                'loc2_picked_qty': self.loc2_picked_qty,
                'loc3_id': self.loc3_id.id,
                'loc3_on_hand_qty': self.loc3_on_hand_qty,
                'loc3_picked_qty': self.loc3_picked_qty,
                'loc8_id': self.loc8_id.id,
                'loc8_on_hand_qty': self.loc8_on_hand_qty,
                'loc8_picked_qty': self.loc8_picked_qty,
            }
        }

    def open_b_plus_wizard(self):
        self.ensure_one()
        return {
            'name': 'B+ Pickup',
            'type': 'ir.actions.act_window',
            'res_model': 'mass.delivery.pickup.wizard.b_plus',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'wizard_id': self.wizard_id.id,
                'move_line_id': self.id,
                'product_id': self.product_id.id,
                'loc7_id': self.loc7_id.id,
                'loc7_on_hand_qty': self.loc7_on_hand_qty,
                'loc7_picked_qty': self.loc7_picked_qty,
                'loc8_id': self.loc8_id.id,
                'loc8_on_hand_qty': self.loc8_on_hand_qty,
                'loc8_picked_qty': self.loc8_picked_qty,
            }
        }

class MassDeliveryPickupWizardFarm(models.TransientModel):
    _name = 'mass.delivery.pickup.wizard.farm'
    _description = 'Mass Delivery Pickup Wizard - Farm Locations'

    wizard_id = fields.Many2one('mass.delivery.pickup.wizard', string="Wizard", required=True)
    move_line_id = fields.Many2one('mass.delivery.pickup.wizard.move', string="Move Line", required=True)
    product_id = fields.Many2one('product.product', string="Product", readonly=True)
    loc1_id = fields.Many2one('stock.location', string="Farm A", readonly=True)
    loc1_on_hand_qty = fields.Float(string="A Avail", readonly=True)
    loc1_picked_qty = fields.Float(string="A Pick Up")
    loc2_id = fields.Many2one('stock.location', string="Farm B", readonly=True)
    loc2_on_hand_qty = fields.Float(string="B Avail", readonly=True)
    loc2_picked_qty = fields.Float(string="B Pick Up")
    loc3_id = fields.Many2one('stock.location', string="Farm UG", readonly=True)
    loc3_on_hand_qty = fields.Float(string="UG Avail", readonly=True)
    loc3_picked_qty = fields.Float(string="UG Pick Up")
    loc8_id = fields.Many2one('stock.location', string="Farm B+", readonly=True)
    loc8_on_hand_qty = fields.Float(string="Farm B+ Available (kg)", readonly=True)
    loc8_picked_qty = fields.Float(string="Farm B+ Pick Up (kg)")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        for field in [
            'wizard_id', 'move_line_id', 'product_id',
            'loc1_id', 'loc1_on_hand_qty', 'loc1_picked_qty',
            'loc2_id', 'loc2_on_hand_qty', 'loc2_picked_qty',
            'loc3_id', 'loc3_on_hand_qty', 'loc3_picked_qty',
            'loc8_id', 'loc8_on_hand_qty', 'loc8_picked_qty',
        ]:
            if ctx.get(field) is not None:
                res[field] = ctx[field]
        return res

    def action_confirm_farm(self):
        self.ensure_one()
        move_line = self.move_line_id
        # Validate picked quantities against available quantities
        for loc_field, qty_field in [
            ('loc1_id', 'loc1_picked_qty'),
            ('loc2_id', 'loc2_picked_qty'),
            ('loc3_id', 'loc3_picked_qty'),
            ('loc8_id', 'loc8_picked_qty'),
        ]:
            loc_id = getattr(self, loc_field)
            picked_qty = getattr(self, qty_field) or 0.0
            on_hand_qty = getattr(self, f'{loc_field.replace("_id", "")}_on_hand_qty')
            if loc_id and picked_qty > on_hand_qty:
                raise ValidationError(
                    _("Picked quantity (%s) for location %s cannot exceed available quantity (%s).") %
                    (picked_qty, loc_id.display_name, on_hand_qty))

        total_picked_qty_stock = sum([
            self.loc1_picked_qty or 0.0,
            self.loc2_picked_qty or 0.0,
            self.loc3_picked_qty or 0.0,
            self.loc8_picked_qty or 0.0,
        ]) + sum([
            move_line.loc4_picked_qty or 0.0,
            move_line.loc5_picked_qty or 0.0,
            move_line.loc6_picked_qty or 0.0,
            move_line.loc7_picked_qty or 0.0,
        ])
        update_vals = {
            'loc1_picked_qty': self.loc1_picked_qty or 0.0,
            'loc2_picked_qty': self.loc2_picked_qty or 0.0,
            'loc3_picked_qty': self.loc3_picked_qty or 0.0,
            'loc8_picked_qty': self.loc8_picked_qty or 0.0,
        }
        # Apply UoM conversion logic
        is_converted_to_KG = False
        picked_qty_so = total_picked_qty_stock
        if move_line.demand_uom_id and not move_line.is_same_uom:
            uom_name = move_line.demand_uom_id.name
            match_gm = re.match(r'PCKT-(\d+)GM$', uom_name)
            match_kg = re.match(r'PCKT-(\d+)KG$', uom_name)
            if match_gm:
                grams = int(match_gm.group(1))
                picked_qty_so = total_picked_qty_stock * 1000 / grams
                is_converted_to_KG = True
            elif match_kg:
                kgrams = int(match_kg.group(1))
                picked_qty_so = total_picked_qty_stock / kgrams
                is_converted_to_KG = True

            # Apply dpw conversion
            dpw_records = self.env['distinct.product.piece.weight'].search([
                ('dpw_product_id', '=', move_line.product_id.id)
            ])
            dpw_record = dpw_records[0] if dpw_records else False
            if not is_converted_to_KG and dpw_record and move_line.demand_uom_id.id == dpw_record.dpw_uom_id.id:
                total_pieces = total_picked_qty_stock * dpw_record.dpw_no_of_pieces_per_unit
                picked_qty_so = total_pieces * dpw_record.dpw_weight_per_piece
                is_converted_to_KG = True

        if move_line.demand_uom_id.id == 12:
            picked_qty_so = total_picked_qty_stock
        update_vals['picked_qty_so'] = picked_qty_so
        move_line.write(update_vals)
        _logger.info("Updated move line %s with farm quantities: %s", move_line.id, update_vals)
        return {'type': 'ir.actions.act_window_close'}

class MassDeliveryPickupWizardBPlus(models.TransientModel):
    _name = 'mass.delivery.pickup.wizard.b_plus'
    _description = 'Mass Delivery Pickup Wizard - B+ Locations'

    wizard_id = fields.Many2one('mass.delivery.pickup.wizard', string="Wizard", required=True)
    move_line_id = fields.Many2one('mass.delivery.pickup.wizard.move', string="Move Line", required=True)
    product_id = fields.Many2one('product.product', string="Product", readonly=True)
    loc7_id = fields.Many2one('stock.location', string="Purchase B+", readonly=True)
    loc7_on_hand_qty = fields.Float(string="Purchase Avail", readonly=True)
    loc7_picked_qty = fields.Float(string="Purchase Pick")
    loc8_id = fields.Many2one('stock.location', string="Farm B+", readonly=True)
    loc8_on_hand_qty = fields.Float(string="Farm Avail", readonly=True)
    loc8_picked_qty = fields.Float(string="Farm Pick")

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        for field in [
            'wizard_id', 'move_line_id', 'product_id',
            'loc7_id', 'loc7_on_hand_qty', 'loc7_picked_qty',
            'loc8_id', 'loc8_on_hand_qty', 'loc8_picked_qty'
        ]:
            if ctx.get(field) is not None:
                res[field] = ctx[field]
        return res

    def action_confirm_b_plus(self):
        self.ensure_one()
        move_line = self.move_line_id
        # Validate picked quantities against available quantities
        for loc_field, qty_field in [
            ('loc7_id', 'loc7_picked_qty'),
            ('loc8_id', 'loc8_picked_qty'),
        ]:
            loc_id = getattr(self, loc_field)
            picked_qty = getattr(self, qty_field) or 0.0
            on_hand_qty = getattr(self, f'{loc_field.replace("_id", "")}_on_hand_qty')
            if loc_id and picked_qty > on_hand_qty:
                raise ValidationError(
                    _("Picked quantity (%s) for location %s cannot exceed available quantity (%s).") %
                    (picked_qty, loc_id.display_name, on_hand_qty))

        total_picked_qty_stock = sum([
            move_line.loc1_picked_qty or 0.0,
            move_line.loc2_picked_qty or 0.0,
            move_line.loc3_picked_qty or 0.0,
            move_line.loc4_picked_qty or 0.0,
            move_line.loc5_picked_qty or 0.0,
            move_line.loc6_picked_qty or 0.0,
            self.loc7_picked_qty or 0.0,
            self.loc8_picked_qty or 0.0,
        ])
        update_vals = {
            'loc7_picked_qty': self.loc7_picked_qty or 0.0,
            'loc8_picked_qty': self.loc8_picked_qty or 0.0,
        }
        # Apply UoM conversion logic
        is_converted_to_KG = False
        picked_qty_so = total_picked_qty_stock
        if move_line.demand_uom_id and not move_line.is_same_uom:
            uom_name = move_line.demand_uom_id.name
            match_gm = re.match(r'PCKT-(\d+)GM$', uom_name)
            match_kg = re.match(r'PCKT-(\d+)KG$', uom_name)
            if match_gm:
                grams = int(match_gm.group(1))
                picked_qty_so = total_picked_qty_stock * 1000 / grams
                is_converted_to_KG = True
            elif match_kg:
                kgrams = int(match_kg.group(1))
                picked_qty_so = total_picked_qty_stock / kgrams
                is_converted_to_KG = True

            # Apply dpw conversion
            dpw_records = self.env['distinct.product.piece.weight'].search([
                ('dpw_product_id', '=', move_line.product_id.id)
            ])
            dpw_record = dpw_records[0] if dpw_records else False
            if not is_converted_to_KG and dpw_record and move_line.demand_uom_id.id == dpw_record.dpw_uom_id.id:
                total_pieces = total_picked_qty_stock * dpw_record.dpw_no_of_pieces_per_unit
                picked_qty_so = total_pieces * dpw_record.dpw_weight_per_piece
                is_converted_to_KG = True

        if move_line.demand_uom_id.id == 12:
            picked_qty_so = total_picked_qty_stock
        update_vals['picked_qty_so'] = picked_qty_so
        move_line.write(update_vals)
        _logger.info("Updated move line %s with B+ quantities: %s", move_line.id, update_vals)
        return {'type': 'ir.actions.act_window_close'}

