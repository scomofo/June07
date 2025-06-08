# bridleal_refactored/app/services/api_clients/quote_builder.py
import logging
from datetime import datetime

# Attempt to import constants for date formats or other defaults
try:
    from app.utils import constants as app_constants
except ImportError:
    app_constants = None

logger = logging.getLogger(__name__)

class QuoteBuilder:
    """
    Builds payload dictionaries for John Deere Quote API requests.
    This class helps in constructing the complex JSON structures required by the API.
    """
    def __init__(self, config=None):
        """
        Initialize the QuoteBuilder.

        Args:
            config (Config, optional): Application configuration, if needed for defaults.
        """
        self.config = config
        self.quote_payload = {}
        logger.info("QuoteBuilder initialized.")

    def new_quote(self):
        """Resets the builder for a new quote payload."""
        self.quote_payload = {
            # Initialize with common top-level keys expected by the JD Quote API
            # These are placeholders and need to match the actual API specification.
            "header": {},
            "summary": {},
            "customer": {},
            "dealer": {},
            "lineItems": [],
            "notes": [],
            "termsAndConditions": {},
            "customFields": [] # Or a dictionary if preferred
        }
        return self # Allow chaining

    def set_header(self, quote_id=None, quote_name=None, status="Draft", version="1", 
                   creation_date=None, last_modified_date=None, created_by=None):
        """
        Sets the header information for the quote.

        Args:
            quote_id (str, optional): Unique identifier for the quote (usually for existing quotes).
            quote_name (str, optional): Name or title of the quote.
            status (str, optional): Status of the quote (e.g., "Draft", "Submitted", "Approved").
            version (str, optional): Version of the quote.
            creation_date (datetime or str, optional): Date of quote creation. ISO format preferred.
            last_modified_date (datetime or str, optional): Date of last modification. ISO format preferred.
            created_by (str, optional): User or system that created the quote.
        """
        header = self.quote_payload.setdefault("header", {})
        if quote_id: header["id"] = quote_id
        if quote_name: header["name"] = quote_name
        header["status"] = status
        header["version"] = version
        
        date_format = getattr(app_constants, 'DATETIME_FORMAT_LOG', '%Y-%m-%dT%H:%M:%S%z') # ISO 8601

        if creation_date:
            header["creationDate"] = creation_date if isinstance(creation_date, str) else creation_date.strftime(date_format)
        else: # Default to now if not provided for a new quote (API might set this)
            header["creationDate"] = datetime.now().strftime(date_format)

        if last_modified_date:
            header["lastModifiedDate"] = last_modified_date if isinstance(last_modified_date, str) else last_modified_date.strftime(date_format)
        else:
            header["lastModifiedDate"] = datetime.now().strftime(date_format)
            
        if created_by: header["createdBy"] = created_by
        
        return self

    def set_customer_info(self, customer_id, name, address=None, contact_person=None, email=None, phone=None):
        """
        Sets customer information.

        Args:
            customer_id (str): Unique identifier for the customer.
            name (str): Customer's name.
            address (dict, optional): Customer's address (e.g., {"street", "city", "state", "zip", "country"}).
            contact_person (str, optional): Name of the contact person.
            email (str, optional): Customer's email.
            phone (str, optional): Customer's phone number.
        """
        customer_info = self.quote_payload.setdefault("customer", {})
        customer_info["id"] = customer_id
        customer_info["name"] = name
        if address: customer_info["address"] = address # Expects a dict
        if contact_person: customer_info["contactPerson"] = contact_person
        if email: customer_info["email"] = email
        if phone: customer_info["phone"] = phone
        return self

    def set_dealer_info(self, dealer_id, branch_id=None, dealer_name=None, salesperson=None):
        """
        Sets dealer and salesperson information.

        Args:
            dealer_id (str): Unique identifier for the dealer.
            branch_id (str, optional): Identifier for the dealer branch.
            dealer_name (str, optional): Name of the dealership.
            salesperson (str, optional): Name or ID of the salesperson.
        """
        dealer_info = self.quote_payload.setdefault("dealer", {})
        dealer_info["id"] = dealer_id
        if branch_id: dealer_info["branchId"] = branch_id
        if dealer_name: dealer_info["name"] = dealer_name
        if salesperson: dealer_info["salesperson"] = salesperson
        return self

    def add_line_item(self, item_id, description, quantity, unit_price, total_price, 
                      product_sku=None, category=None, notes=None, custom_fields=None):
        """
        Adds a line item to the quote.

        Args:
            item_id (str): Unique identifier for this line item within the quote.
            description (str): Description of the item.
            quantity (float or int): Quantity of the item.
            unit_price (float): Price per unit.
            total_price (float): Total price for this line item (quantity * unit_price, potentially with discounts).
            product_sku (str, optional): SKU or product code.
            category (str, optional): Category of the item.
            notes (str, optional): Specific notes for this line item.
            custom_fields (dict, optional): Any custom fields for this line item.
        """
        line_item = {
            "id": item_id,
            "description": description,
            "quantity": quantity,
            "unitPrice": unit_price,
            "totalPrice": total_price
        }
        if product_sku: line_item["sku"] = product_sku
        if category: line_item["category"] = category
        if notes: line_item["notes"] = notes
        if custom_fields: line_item["customFields"] = custom_fields # Expects a dict

        self.quote_payload.setdefault("lineItems", []).append(line_item)
        return self

    def set_summary(self, subtotal, tax_amount=0.0, discount_amount=0.0, shipping_cost=0.0, grand_total=None, currency="USD"):
        """
        Sets the financial summary of the quote.

        Args:
            subtotal (float): Subtotal of all line items.
            tax_amount (float, optional): Total tax amount. Defaults to 0.0.
            discount_amount (float, optional): Total discount amount. Defaults to 0.0.
            shipping_cost (float, optional): Shipping and handling costs. Defaults to 0.0.
            grand_total (float, optional): The final total amount. If None, it's calculated.
            currency (str, optional): Currency code (e.g., "USD", "CAD"). Defaults to "USD".
        """
        summary = self.quote_payload.setdefault("summary", {})
        summary["subtotal"] = subtotal
        summary["taxAmount"] = tax_amount
        summary["discountAmount"] = discount_amount
        summary["shippingCost"] = shipping_cost
        
        if grand_total is None:
            calculated_total = subtotal + tax_amount - discount_amount + shipping_cost
            summary["grandTotal"] = calculated_total
        else:
            summary["grandTotal"] = grand_total
            
        summary["currency"] = currency
        return self

    def add_note(self, note_text, author=None, date_added=None):
        """
        Adds a general note to the quote.

        Args:
            note_text (str): The content of the note.
            author (str, optional): Author of the note.
            date_added (datetime or str, optional): Date the note was added. ISO format preferred.
        """
        note = {"text": note_text}
        if author: note["author"] = author
        
        date_format = getattr(app_constants, 'DATETIME_FORMAT_LOG', '%Y-%m-%dT%H:%M:%S%z')
        if date_added:
            note["dateAdded"] = date_added if isinstance(date_added, str) else date_added.strftime(date_format)
        else:
            note["dateAdded"] = datetime.now().strftime(date_format)
            
        self.quote_payload.setdefault("notes", []).append(note)
        return self

    def set_terms_and_conditions(self, text, version=None):
        """
        Sets the terms and conditions for the quote.

        Args:
            text (str): The full text of terms and conditions.
            version (str, optional): Version of the terms.
        """
        terms = self.quote_payload.setdefault("termsAndConditions", {})
        terms["text"] = text
        if version: terms["version"] = version
        return self
        
    def add_custom_field(self, field_name, field_value, field_type="string"):
        """
        Adds a custom field to the quote (at the top level).

        Args:
            field_name (str): The name (key) of the custom field.
            field_value (any): The value of the custom field.
            field_type (str, optional): The data type of the field (e.g., "string", "number", "boolean", "date").
        """
        custom_field_entry = {
            "name": field_name,
            "value": field_value,
            "type": field_type
        }
        # Or if customFields is a dict: self.quote_payload.setdefault("customFields", {})[field_name] = field_value
        self.quote_payload.setdefault("customFields", []).append(custom_field_entry)
        return self

    def build(self):
        """
        Returns the constructed quote payload dictionary.
        Performs any final validation or calculations if needed.
        """
        # Example: Ensure summary grandTotal is calculated if not explicitly set
        summary = self.quote_payload.get("summary", {})
        if "grandTotal" not in summary and "subtotal" in summary:
            subtotal = summary.get("subtotal", 0.0)
            tax = summary.get("taxAmount", 0.0)
            discount = summary.get("discountAmount", 0.0)
            shipping = summary.get("shippingCost", 0.0)
            summary["grandTotal"] = subtotal + tax - discount + shipping
            logger.debug("Calculated grandTotal in build step.")

        logger.info("Quote payload built.")
        # import json # For pretty printing during debug
        # logger.debug(f"Final Payload: {json.dumps(self.quote_payload, indent=2)}")
        return self.quote_payload

# Example Usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    import json

    builder = QuoteBuilder()

    quote = (builder.new_quote()
             .set_header(quote_name="Large Tractor Deal Q2", created_by="SalesBot")
             .set_customer_info(customer_id="CUST-001", name="GreenAcres Farm",
                                address={"street": "123 Farm Rd", "city": "RuralVille", "state": "ST", "zip": "12345"},
                                email="contact@greenacres.com")
             .set_dealer_info(dealer_id="DEALER-789", branch_id="BRANCH-A", salesperson="John Doe")
             .add_line_item(item_id="LI-001", description="Model X SuperTractor", quantity=1,
                            unit_price=75000.00, total_price=75000.00, product_sku="TR-MODX-ST")
             .add_line_item(item_id="LI-002", description="Plow Attachment Package", quantity=1,
                            unit_price=5000.00, total_price=4800.00, product_sku="PL-PKG-01", notes="Includes 10% discount")
             .set_summary(subtotal=80000.00, tax_amount=6400.00, discount_amount=200.00, shipping_cost=500.00, currency="USD")
             .add_note("Customer interested in financing options.", author="John Doe")
             .set_terms_and_conditions("Standard 30-day payment terms. Warranty detailed in separate document.", version="1.1")
             .add_custom_field(field_name="FinancingRequired", field_value=True, field_type="boolean")
             .add_custom_field(field_name="DeliveryPreference", field_value="ASAP")
             .build())

    logger.info("Generated Quote Payload:")
    # Pretty print the JSON
    print(json.dumps(quote, indent=4))

    # Example of building a minimal quote
    minimal_builder = QuoteBuilder()
    minimal_quote = (minimal_builder.new_quote()
                     .set_header(quote_name="Quick Add")
                     .set_customer_info(customer_id="CUST-MIN", name="Minimal Farms")
                     .add_line_item("M-LI-1", "Seed Pack", 10, 20.0, 200.0)
                     .set_summary(subtotal=200.0, grand_total=210.0, tax_amount=10.0) # Explicit grand_total
                     .build())
    logger.info("\nGenerated Minimal Quote Payload:")
    print(json.dumps(minimal_quote, indent=4))
