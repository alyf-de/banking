import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	click.echo("Installing Klarna Kosma Custom Fields ...")
	create_custom_fields(frappe.get_hooks("kosma_custom_fields"))
