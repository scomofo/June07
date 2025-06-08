import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import datetime
from datetime import datetime
import os

class MaintainQuoteWindow:
    """
    Window for managing quotes through the Maintain Quote API
    """

    def __init__(self, root, config_manager, maintain_quote_client, quote_client=None):
        """
        Initialize the maintain quote window

        Args:
            root: Tkinter root window
            config_manager: Configuration manager
            maintain_quote_client: Maintain Quote API client
            quote_client: Optional Quote API client for additional functionality
        """
        self.root = root
        self.config = config_manager
        self.maintain_quote_client = maintain_quote_client
        self.quote_client = quote_client

        self.setup_ui()

    def setup_ui(self):
        """
        Set up the user interface
        """
        self.root.title("JD Maintain Quote Manager")
        self.root.geometry("1200x800")

        # Create a notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.create_quote_tab = ttk.Frame(self.notebook)
        self.edit_quote_tab = ttk.Frame(self.notebook)
        self.equipment_tab = ttk.Frame(self.notebook)
        self.trade_in_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.create_quote_tab, text="Create Quote")
        self.notebook.add(self.edit_quote_tab, text="Edit Quote")
        self.notebook.add(self.equipment_tab, text="Equipment")
        self.notebook.add(self.trade_in_tab, text="Trade-In")
        self.notebook.add(self.settings_tab, text="Settings")

        # Set up each tab
        self.setup_create_quote_tab()
        self.setup_edit_quote_tab()
        self.setup_equipment_tab()
        self.setup_trade_in_tab()
        self.setup_settings_tab()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def setup_create_quote_tab(self):
        """
        Set up the create quote tab
        """
        # Left side - form for quote creation
        form_frame = ttk.LabelFrame(self.create_quote_tab, text="Create New Quote")
        form_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create a frame for the form fields
        fields_frame = ttk.Frame(form_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dealer information
        ttk.Label(fields_frame, text="Dealer Information", font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(fields_frame, text="Dealer ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.dealer_id_var = tk.StringVar(value=self.config.get("api", "dealer_id", ""))
        ttk.Entry(fields_frame, textvariable=self.dealer_id_var, width=20).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Dealer Account:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.dealer_account_var = tk.StringVar(value=self.config.get("api", "dealer_account_number", ""))
        ttk.Entry(fields_frame, textvariable=self.dealer_account_var, width=20).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Quote information
        ttk.Label(fields_frame, text="Quote Information", font=("", 10, "bold")).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(fields_frame, text="Quote Name:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.quote_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.quote_name_var, width=30).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Quote Type:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.quote_type_var = tk.StringVar()
        ttk.Combobox(fields_frame, textvariable=self.quote_type_var, values=["Purchase", "Lease", "Rental"], width=15).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)

        # Customer information
        ttk.Label(fields_frame, text="Customer Information", font=("", 10, "bold")).grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(fields_frame, text="First Name:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        self.customer_first_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.customer_first_name_var, width=30).grid(row=7, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Last Name:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=2)
        self.customer_last_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.customer_last_name_var, width=30).grid(row=8, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Business Name:").grid(row=9, column=0, sticky=tk.W, padx=5, pady=2)
        self.customer_business_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.customer_business_var, width=30).grid(row=9, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Email:").grid(row=10, column=0, sticky=tk.W, padx=5, pady=2)
        self.customer_email_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.customer_email_var, width=30).grid(row=10, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Phone:").grid(row=11, column=0, sticky=tk.W, padx=5, pady=2)
        self.customer_phone_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.customer_phone_var, width=20).grid(row=11, column=1, sticky=tk.W, padx=5, pady=2)

        # Expiration date
        ttk.Label(fields_frame, text="Expiration Date:").grid(row=12, column=0, sticky=tk.W, padx=5, pady=2)

        # Calculate expiration date (30 days from now)
        expiration_date = (datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        self.expiration_date_var = tk.StringVar(value=expiration_date)
        ttk.Entry(fields_frame, textvariable=self.expiration_date_var, width=12).grid(row=12, column=1, sticky=tk.W, padx=5, pady=2)

        # Create Quote button
        self.create_button = ttk.Button(fields_frame, text="Create Quote", command=self.create_quote)
        self.create_button.grid(row=14, column=1, sticky=tk.E, padx=5, pady=10)

        # Clear button
        self.clear_button = ttk.Button(fields_frame, text="Clear Form", command=self.clear_create_form)
        self.clear_button.grid(row=14, column=0, sticky=tk.W, padx=5, pady=10)

        # Right side - JSON preview
        preview_frame = ttk.LabelFrame(self.create_quote_tab, text="JSON Preview")
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add a button to refresh the JSON preview
        refresh_button = ttk.Button(preview_frame, text="Refresh Preview", command=self.refresh_json_preview)
        refresh_button.pack(fill=tk.X, padx=5, pady=5)

        # Add a text widget to display the JSON
        self.json_preview = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, width=50, height=30)
        self.json_preview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Initialize the JSON preview
        self.refresh_json_preview()

    def setup_edit_quote_tab(self):
        """
        Set up the edit quote tab
        """
        # Top section - quote selection
        selection_frame = ttk.Frame(self.edit_quote_tab)
        selection_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selection_frame, text="Quote ID:").pack(side=tk.LEFT, padx=5)
        self.edit_quote_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=self.edit_quote_id_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(selection_frame, text="Load Quote", command=self.load_quote_for_edit).pack(side=tk.LEFT, padx=5)

        # Main section - split view for form and JSON
        main_frame = ttk.Frame(self.edit_quote_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side - form for quote editing
        form_frame = ttk.LabelFrame(main_frame, text="Edit Quote")
        form_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create a frame for the form fields
        fields_frame = ttk.Frame(form_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Quote information
        ttk.Label(fields_frame, text="Quote Information", font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(fields_frame, text="Quote Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_quote_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.edit_quote_name_var, width=30).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Quote Type:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_quote_type_var = tk.StringVar()
        ttk.Combobox(fields_frame, textvariable=self.edit_quote_type_var, values=["Purchase", "Lease", "Rental"], width=15).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Customer information
        ttk.Label(fields_frame, text="Customer Information", font=("", 10, "bold")).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(fields_frame, text="First Name:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_customer_first_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.edit_customer_first_name_var, width=30).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Last Name:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_customer_last_name_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.edit_customer_last_name_var, width=30).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Business Name:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_customer_business_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.edit_customer_business_var, width=30).grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)

        # Expiration date
        ttk.Label(fields_frame, text="Expiration Date:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        self.edit_expiration_date_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.edit_expiration_date_var, width=12).grid(row=7, column=1, sticky=tk.W, padx=5, pady=2)

        # Update Quote button
        self.update_button = ttk.Button(fields_frame, text="Update Quote", command=self.update_quote)
        self.update_button.grid(row=9, column=1, sticky=tk.E, padx=5, pady=10)

        # Save Quote button
        self.save_button = ttk.Button(fields_frame, text="Save Quote", command=self.save_quote)
        self.save_button.grid(row=9, column=0, sticky=tk.W, padx=5, pady=10)

        # Delete Quote button
        self.delete_button = ttk.Button(fields_frame, text="Delete Quote", command=self.delete_quote)
        self.delete_button.grid(row=10, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        # Right side - JSON editor
        json_frame = ttk.LabelFrame(main_frame, text="JSON Editor")
        json_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add a text widget for editing JSON
        self.edit_json_editor = scrolledtext.ScrolledText(json_frame, wrap=tk.WORD, width=50, height=30)
        self.edit_json_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add buttons for JSON operations
        json_buttons_frame = ttk.Frame(json_frame)
        json_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(json_buttons_frame, text="Update Form from JSON", command=self.update_form_from_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(json_buttons_frame, text="Format JSON", command=self.format_json).pack(side=tk.LEFT, padx=5)
        ttk.Button(json_buttons_frame, text="Apply JSON", command=self.apply_json_edit).pack(side=tk.RIGHT, padx=5)

    def setup_equipment_tab(self):
        """
        Set up the equipment tab
        """
        # Top section - quote selection
        selection_frame = ttk.Frame(self.equipment_tab)
        selection_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selection_frame, text="Quote ID:").pack(side=tk.LEFT, padx=5)
        self.equipment_quote_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=self.equipment_quote_id_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(selection_frame, text="Load Equipment", command=self.load_equipment).pack(side=tk.LEFT, padx=5)

        # Main section - split view for equipment list and equipment form
        main_frame = ttk.Frame(self.equipment_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side - equipment list
        list_frame = ttk.LabelFrame(main_frame, text="Equipment List")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview for equipment list
        columns = ("ID", "Model", "Description", "Quantity", "Price")
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        # Set column headings
        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=100)

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=y_scrollbar.set)

        # Pack treeview and scrollbar
        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.equipment_tree.bind("<<TreeviewSelect>>", self.equipment_selected)

        # Right side - equipment form
        form_frame = ttk.LabelFrame(main_frame, text="Equipment Details")
        form_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create a frame for the form fields
        fields_frame = ttk.Frame(form_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Equipment ID (hidden, for tracking purposes)
        self.equipment_id_var = tk.StringVar()

        # Equipment details
        ttk.Label(fields_frame, text="Model Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.equipment_model_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.equipment_model_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.equipment_description_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.equipment_description_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Quantity:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.equipment_quantity_var = tk.StringVar(value="1")
        ttk.Spinbox(fields_frame, from_=1, to=100, textvariable=self.equipment_quantity_var, width=5).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Price:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.equipment_price_var = tk.StringVar(value="0.00")
        ttk.Entry(fields_frame, textvariable=self.equipment_price_var, width=15).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Buttons
        buttons_frame = ttk.Frame(fields_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        ttk.Button(buttons_frame, text="Add Equipment", command=self.add_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Update Equipment", command=self.update_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Delete Equipment", command=self.delete_equipment).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Clear Form", command=self.clear_equipment_form).pack(side=tk.RIGHT, padx=5)

    def setup_trade_in_tab(self):
        """
        Set up the trade-in tab
        """
        # Top section - quote selection
        selection_frame = ttk.Frame(self.trade_in_tab)
        selection_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(selection_frame, text="Quote ID:").pack(side=tk.LEFT, padx=5)
        self.trade_in_quote_id_var = tk.StringVar()
        ttk.Entry(selection_frame, textvariable=self.trade_in_quote_id_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(selection_frame, text="Load Trade-Ins", command=self.load_trade_ins).pack(side=tk.LEFT, padx=5)

        # Main section - split view for trade-in list and trade-in form
        main_frame = ttk.Frame(self.trade_in_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side - trade-in list
        list_frame = ttk.LabelFrame(main_frame, text="Trade-In List")
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create treeview for trade-in list
        columns = ("ID", "Model", "Description", "Serial Number", "Value")
        self.trade_in_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        # Set column headings
        for col in columns:
            self.trade_in_tree.heading(col, text=col)
            self.trade_in_tree.column(col, width=100)

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.trade_in_tree.yview)
        self.trade_in_tree.configure(yscrollcommand=y_scrollbar.set)

        # Pack treeview and scrollbar
        self.trade_in_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection event
        self.trade_in_tree.bind("<<TreeviewSelect>>", self.trade_in_selected)

        # Right side - trade-in form
        form_frame = ttk.LabelFrame(main_frame, text="Trade-In Details")
        form_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create a frame for the form fields
        fields_frame = ttk.Frame(form_frame)
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Trade-in ID (hidden, for tracking purposes)
        self.trade_in_id_var = tk.StringVar()

        # Trade-in details
        ttk.Label(fields_frame, text="Model Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.trade_in_model_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.trade_in_model_var, width=30).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.trade_in_description_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.trade_in_description_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Serial Number:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.trade_in_serial_var = tk.StringVar()
        ttk.Entry(fields_frame, textvariable=self.trade_in_serial_var, width=20).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(fields_frame, text="Value:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.trade_in_value_var = tk.StringVar(value="0.00")
        ttk.Entry(fields_frame, textvariable=self.trade_in_value_var, width=15).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Buttons
        buttons_frame = ttk.Frame(fields_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        ttk.Button(buttons_frame, text="Add Trade-In", command=self.add_trade_in).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Update Trade-In", command=self.update_trade_in).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Clear Form", command=self.clear_trade_in_form).pack(side=tk.RIGHT, padx=5)

    # Create Quote Tab Methods
    def refresh_json_preview(self):
        """
        Refresh the JSON preview based on the current form values
        """
        try:
            # Build quote data from form fields
            quote_data = self.build_quote_data_from_form()

            # Format as JSON
            json_text = json.dumps(quote_data, indent=4)

            # Update the preview
            self.json_preview.delete(1.0, tk.END)
            self.json_preview.insert(tk.END, json_text)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate JSON preview: {str(e)}")

    def build_quote_data_from_form(self):
        """
        Build quote data from the form fields

        Returns:
            dict: Quote data
        """
        # Parse expiration date
        try:
            expiration_date = datetime.strptime(self.expiration_date_var.get(), "%Y-%m-%d")
            formatted_expiration = expiration_date.strftime("%d-%b-%y").upper()
        except ValueError:
            formatted_expiration = ""

        # Build quote data
        return {
            "quoteName": self.quote_name_var.get(),
            "quoteType": self.quote_type_var.get(),
            "dealerAccountNumber": self.dealer_account_var.get(),
            "customer": {
                "firstName": self.customer_first_name_var.get(),
                "lastName": self.customer_last_name_var.get(),
                "businessName": self.customer_business_var.get(),
                "email": self.customer_email_var.get(),
                "phone": self.customer_phone_var.get()
            },
            "expirationDate": formatted_expiration,
            # Add other fields as needed
        }

    def clear_create_form(self):
        """
        Clear the create quote form
        """
        self.quote_name_var.set("")
        self.quote_type_var.set("")
        self.customer_first_name_var.set("")
        self.customer_last_name_var.set("")
        self.customer_business_var.set("")
        self.customer_email_var.set("")
        self.customer_phone_var.set("")

        # Reset expiration date to default (30 days from now)
        expiration_date = (datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        self.expiration_date_var.set(expiration_date)

        # Refresh the JSON preview
        self.refresh_json_preview()

        self.status_var.set("Form cleared.")

    def create_quote(self):
        """
        Create a new quote
        """
        try:
            self.status_var.set("Creating quote...")

            # Build quote data from form fields
            quote_data = self.build_quote_data_from_form()

            # Call the API to create the quote
            dealer_id = self.dealer_id_var.get()
            if not dealer_id:
                messagebox.showerror("Error", "Dealer ID is required.")
                return

            result = self.maintain_quote_client.create_dealer_quote(dealer_id, quote_data)

            # Check if the quote was created successfully
            if "body" in result and "quoteID" in result["body"]:
                quote_id = result["body"]["quoteID"]
                messagebox.showinfo("Success", f"Quote created successfully.\nQuote ID: {quote_id}")

                # Update the quote ID fields in other tabs
                self.edit_quote_id_var.set(quote_id)
                self.equipment_quote_id_var.set(quote_id)
                self.trade_in_quote_id_var.set(quote_id)

                # Switch to the edit tab
                self.notebook.select(self.edit_quote_tab)

                # Load the quote details
                self.load_quote_for_edit()

                self.status_var.set(f"Quote {quote_id} created.")
            else:
                messagebox.showwarning("Warning", "Quote creation response did not contain a Quote ID.")
                self.status_var.set("Quote creation completed, but no Quote ID was returned.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create quote: {str(e)}")
            self.status_var.set("Error creating quote.")

    # Edit Quote Tab Methods
    def load_quote_for_edit(self):
        """
        Load a quote for editing
        """
        quote_id = self.edit_quote_id_var.get()
        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        try:
            self.status_var.set(f"Loading quote {quote_id}...")

            # Get quote details from the API
            quote_details = self.maintain_quote_client.get_quote_details(quote_id)

            # Check if the response contains quote details
            if "body" not in quote_details or not quote_details["body"]:
                messagebox.showinfo("Information", f"No details found for Quote ID: {quote_id}")
                self.status_var.set("No quote details found.")
                return

            # Extract quote data
            quote = quote_details["body"]

            # Update form fields
            self.edit_quote_name_var.set(quote.get("quoteName", ""))
            self.edit_quote_type_var.set(quote.get("quoteType", ""))

            # Customer information
            customer = quote.get("customer", {})
            self.edit_customer_first_name_var.set(customer.get("firstName", ""))
            self.edit_customer_last_name_var.set(customer.get("lastName", ""))
            self.edit_customer_business_var.set(customer.get("businessName", ""))

            # Expiration date
            expiration_date = quote.get("expirationDate", "")
            if expiration_date:
                try:
                    # Convert from API format to YYYY-MM-DD
                    date_obj = datetime.strptime(expiration_date, "%d-%b-%y")
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                    self.edit_expiration_date_var.set(formatted_date)
                except ValueError:
                    self.edit_expiration_date_var.set(expiration_date)

            # Update the JSON editor
            json_text = json.dumps(quote, indent=4)
            self.edit_json_editor.delete(1.0, tk.END)
            self.edit_json_editor.insert(tk.END, json_text)

            # Update the equipment and trade-in quote IDs
            self.equipment_quote_id_var.set(quote_id)
            self.trade_in_quote_id_var.set(quote_id)

            self.status_var.set(f"Loaded quote: {quote_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load quote details: {str(e)}")
            self.status_var.set("Error loading quote details.")

    def update_form_from_json(self):
        """
        Update the form fields from the JSON editor
        """
        try:
            # Get the JSON from the editor
            json_text = self.edit_json_editor.get(1.0, tk.END).strip()
            if not json_text:
                return

            # Parse the JSON
            quote = json.loads(json_text)

            # Update form fields
            self.edit_quote_name_var.set(quote.get("quoteName", ""))
            self.edit_quote_type_var.set(quote.get("quoteType", ""))

            # Customer information
            customer = quote.get("customer", {})
            self.edit_customer_first_name_var.set(customer.get("firstName", ""))
            self.edit_customer_last_name_var.set(customer.get("lastName", ""))
            self.edit_customer_business_var.set(customer.get("businessName", ""))

            # Expiration date
            expiration_date = quote.get("expirationDate", "")
            if expiration_date:
                try:
                    # Convert from API format to YYYY-MM-DD
                    date_obj = datetime.strptime(expiration_date, "%d-%b-%y")
                    formatted_date = date_obj.strftime("%Y-%m-%d")
                    self.edit_expiration_date_var.set(formatted_date)
                except ValueError:
                    self.edit_expiration_date_var.set(expiration_date)

            self.status_var.set("Form updated from JSON.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update form from JSON: {str(e)}")
            self.status_var.set("Error updating form from JSON.")

    def format_json(self):
        """
        Format the JSON in the editor
        """
        try:
            # Get the JSON from the editor
            json_text = self.edit_json_editor.get(1.0, tk.END).strip()
            if not json_text:
                return

            # Parse and format the JSON
            parsed_json = json.loads(json_text)
            formatted_json = json.dumps(parsed_json, indent=4)

            # Update the editor
            self.edit_json_editor.delete(1.0, tk.END)
            self.edit_json_editor.insert(tk.END, formatted_json)

            self.status_var.set("JSON formatted.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to format JSON: {str(e)}")
            self.status_var.set("Error formatting JSON.")

    def apply_json_edit(self):
        """
        Apply the JSON edits to the quote
        """
        try:
            # Get the quote ID
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showinfo("Information", "Please load a quote first.")
                return

            # Get the JSON from the editor
            json_text = self.edit_json_editor.get(1.0, tk.END).strip()
            if not json_text:
                messagebox.showinfo("Information", "No JSON data to apply.")
                return

            # Parse the JSON
            quote_data = json.loads(json_text)

            # Confirm with the user
            confirm = messagebox.askyesno("Confirm", "Are you sure you want to apply these JSON edits to the quote?")
            if not confirm:
                return

            # Call the API to update the quote
            result = self.maintain_quote_client.update_quote(quote_id, quote_data)

            # Check if the update was successful
            if "body" in result:
                messagebox.showinfo("Success", "Quote updated successfully.")

                # Reload the quote
                self.load_quote_for_edit()

                self.status_var.set(f"Quote {quote_id} updated.")
            else:
                messagebox.showwarning("Warning", "Quote update response did not contain expected data.")
                self.status_var.set("Quote update completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply JSON edits: {str(e)}")
            self.status_var.set("Error applying JSON edits.")

    def update_quote(self):
        """
        Update the quote with the form values
        """
        try:
            # Get the quote ID
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showinfo("Information", "Please load a quote first.")
                return

            # Build quote data from form fields
            quote_data = self.build_edit_quote_data_from_form()

            # Call the API to update the quote
            result = self.maintain_quote_client.update_quote(quote_id, quote_data)

            # Check if the update was successful
            if "body" in result:
                messagebox.showinfo("Success", "Quote updated successfully.")

                # Reload the quote
                self.load_quote_for_edit()

                self.status_var.set(f"Quote {quote_id} updated.")
            else:
                messagebox.showwarning("Warning", "Quote update response did not contain expected data.")
                self.status_var.set("Quote update completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update quote: {str(e)}")
            self.status_var.set("Error updating quote.")

    def build_edit_quote_data_from_form(self):
        """
        Build quote data from the edit form fields

        Returns:
            dict: Quote data
        """
        # Parse expiration date
        try:
            expiration_date = datetime.strptime(self.edit_expiration_date_var.get(), "%Y-%m-%d")
            formatted_expiration = expiration_date.strftime("%d-%b-%y").upper()
        except ValueError:
            formatted_expiration = ""

        # Build quote data
        return {
            "quoteName": self.edit_quote_name_var.get(),
            "quoteType": self.edit_quote_type_var.get(),
            "customer": {
                "firstName": self.edit_customer_first_name_var.get(),
                "lastName": self.edit_customer_last_name_var.get(),
                "businessName": self.edit_customer_business_var.get()
            },
            "expirationDate": formatted_expiration,
            # Add other fields as needed
        }

    def save_quote(self):
        """
        Save the quote
        """
        try:
            # Get the quote ID
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showinfo("Information", "Please load a quote first.")
                return

            # Build quote data from form fields
            quote_data = self.build_edit_quote_data_from_form()

            # Call the API to save the quote
            result = self.maintain_quote_client.save_quote(quote_id, quote_data)

            # Check if the save was successful
            if "body" in result:
                messagebox.showinfo("Success", "Quote saved successfully.")

                # Reload the quote
                self.load_quote_for_edit()

                self.status_var.set(f"Quote {quote_id} saved.")
            else:
                messagebox.showwarning("Warning", "Quote save response did not contain expected data.")
                self.status_var.set("Quote save completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save quote: {str(e)}")
            self.status_var.set("Error saving quote.")

    def delete_quote(self):
        """
        Delete the quote
        """
        try:
            # Get the quote ID
            quote_id = self.edit_quote_id_var.get()
            if not quote_id:
                messagebox.showinfo("Information", "Please load a quote first.")
                return

            # Get the dealer ID
            dealer_id = self.config.get("api", "dealer_id", "")
            if not dealer_id:
                messagebox.showerror("Error", "Dealer ID is required to delete a quote.")
                return

            # Confirm with the user
            confirm = messagebox.askyesno("Confirm", f"Are you sure you want to delete Quote {quote_id}? This action cannot be undone.")
            if not confirm:
                return

            # Call the API to delete the quote
            result = self.maintain_quote_client.delete_quote(quote_id, dealer_id)

            # Check if the delete was successful
            messagebox.showinfo("Success", "Quote deleted successfully.")

            # Clear the form
            self.edit_quote_id_var.set("")
            self.edit_quote_name_var.set("")
            self.edit_quote_type_var.set("")
            self.edit_customer_first_name_var.set("")
            self.edit_customer_last_name_var.set("")
            self.edit_customer_business_var.set("")
            self.edit_expiration_date_var.set("")

            # Clear the JSON editor
            self.edit_json_editor.delete(1.0, tk.END)

            self.status_var.set(f"Quote {quote_id} deleted.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete quote: {str(e)}")
            self.status_var.set("Error deleting quote.")

    # Equipment Tab Methods
    def load_equipment(self):
        """
        Load equipment for a quote
        """
        quote_id = self.equipment_quote_id_var.get()
        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        try:
            self.status_var.set(f"Loading equipment for quote {quote_id}...")

            # Get quote details from the API
            quote_details = self.maintain_quote_client.get_quote_details(quote_id)

            # Check if the response contains quote details
            if "body" not in quote_details or not quote_details["body"]:
                messagebox.showinfo("Information", f"No details found for Quote ID: {quote_id}")
                self.status_var.set("No quote details found.")
                return

            # Extract equipment data
            equipment_list = quote_details["body"].get("equipment", [])

            # Clear the current equipment list
            for item in self.equipment_tree.get_children():
                self.equipment_tree.delete(item)

            # Populate the equipment list
            for equipment in equipment_list:
                self.equipment_tree.insert("", tk.END, values=(
                    equipment.get("equipmentID", ""),
                    equipment.get("modelName", ""),
                    equipment.get("description", ""),
                    equipment.get("quantity", ""),
                    equipment.get("price", "")
                ))

            self.status_var.set(f"Loaded {len(equipment_list)} equipment items for quote {quote_id}.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load equipment: {str(e)}")
            self.status_var.set("Error loading equipment.")

    def equipment_selected(self, event):
        """
        Handle equipment selection event

        Args:
            event: The event that triggered this function
        """
        selected_item = self.equipment_tree.selection()
        if not selected_item:
            return

        # Get the equipment data from the selected item
        item_values = self.equipment_tree.item(selected_item[0], "values")

        # Update the form fields
        self.equipment_id_var.set(item_values[0])
        self.equipment_model_var.set(item_values[1])
        self.equipment_description_var.set(item_values[2])
        self.equipment_quantity_var.set(item_values[3])
        self.equipment_price_var.set(item_values[4])

    def clear_equipment_form(self):
        """
        Clear the equipment form
        """
        self.equipment_id_var.set("")
        self.equipment_model_var.set("")
        self.equipment_description_var.set("")
        self.equipment_quantity_var.set("1")
        self.equipment_price_var.set("0.00")

        # Clear the selection in the tree
        self.equipment_tree.selection_remove(self.equipment_tree.selection())

        self.status_var.set("Equipment form cleared.")

    def add_equipment(self):
        """
        Add equipment to a quote
        """
        quote_id = self.equipment_quote_id_var.get()
        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        try:
            self.status_var.set("Adding equipment...")

            # Build equipment data from form fields
            equipment_data = {
                "equipment": [{
                    "modelName": self.equipment_model_var.get(),
                    "description": self.equipment_description_var.get(),
                    "quantity": int(self.equipment_quantity_var.get()),
                    "price": float(self.equipment_price_var.get())
                }]
            }

            # Call the API to add equipment
            result = self.maintain_quote_client.add_equipment(quote_id, equipment_data)

            # Check if the equipment was added successfully
            if "body" in result:
                messagebox.showinfo("Success", "Equipment added successfully.")

                # Reload the equipment list
                self.load_equipment()

                # Clear the form
                self.clear_equipment_form()

                self.status_var.set("Equipment added.")
            else:
                messagebox.showwarning("Warning", "Equipment addition response did not contain expected data.")
                self.status_var.set("Equipment addition completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add equipment: {str(e)}")
            self.status_var.set("Error adding equipment.")

    def update_equipment(self):
        """
        Update equipment in a quote
        """
        quote_id = self.equipment_quote_id_var.get()
        equipment_id = self.equipment_id_var.get()

        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        if not equipment_id:
            messagebox.showinfo("Information", "Please select an equipment item to update.")
            return

        try:
            self.status_var.set("Updating equipment...")

            # Build equipment data from form fields
            equipment_data = {
                "equipment": [{
                    "equipmentID": equipment_id,
                    "modelName": self.equipment_model_var.get(),
                    "description": self.equipment_description_var.get(),
                    "quantity": int(self.equipment_quantity_var.get()),
                    "price": float(self.equipment_price_var.get())
                }]
            }

            # Call the API to update equipment
            # Since there's no specific "update equipment" endpoint, we'll use add_equipment with the equipmentID set
            result = self.maintain_quote_client.add_equipment(quote_id, equipment_data)

            # Check if the equipment was updated successfully
            if "body" in result:
                messagebox.showinfo("Success", "Equipment updated successfully.")

                # Reload the equipment list
                self.load_equipment()

                # Clear the form
                self.clear_equipment_form()

                self.status_var.set("Equipment updated.")
            else:
                messagebox.showwarning("Warning", "Equipment update response did not contain expected data.")
                self.status_var.set("Equipment update completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update equipment: {str(e)}")
            self.status_var.set("Error updating equipment.")

    def delete_equipment(self):
        """
        Delete equipment from a quote
        """
        quote_id = self.equipment_quote_id_var.get()
        equipment_id = self.equipment_id_var.get()

        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        if not equipment_id:
            messagebox.showinfo("Information", "Please select an equipment item to delete.")
            return

        try:
            self.status_var.set("Deleting equipment...")

            # Confirm with the user
            confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this equipment item?")
            if not confirm:
                return

            # Build equipment data for deletion
            equipment_data = {
                "equipment": [{
                    "equipmentID": equipment_id
                }]
            }

            # Call the API to delete equipment
            result = self.maintain_quote_client.delete_equipment(quote_id, equipment_data)

            # Check if the equipment was deleted successfully
            messagebox.showinfo("Success", "Equipment deleted successfully.")

            # Reload the equipment list
            self.load_equipment()

            # Clear the form
            self.clear_equipment_form()

            self.status_var.set("Equipment deleted.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete equipment: {str(e)}")
            self.status_var.set("Error deleting equipment.")

    # Trade-In Tab Methods
    def load_trade_ins(self):
        """
        Load trade-ins for a quote
        """
        quote_id = self.trade_in_quote_id_var.get()
        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        try:
            self.status_var.set(f"Loading trade-ins for quote {quote_id}...")

            # Get quote details from the API
            quote_details = self.maintain_quote_client.get_quote_details(quote_id)

            # Check if the response contains quote details
            if "body" not in quote_details or not quote_details["body"]:
                messagebox.showinfo("Information", f"No details found for Quote ID: {quote_id}")
                self.status_var.set("No quote details found.")
                return

            # Extract trade-in data
            trade_in_list = quote_details["body"].get("tradeIns", [])

            # Clear the current trade-in list
            for item in self.trade_in_tree.get_children():
                self.trade_in_tree.delete(item)

            # Populate the trade-in list
            for trade_in in trade_in_list:
                self.trade_in_tree.insert("", tk.END, values=(
                    trade_in.get("tradeInID", ""),
                    trade_in.get("modelName", ""),
                    trade_in.get("description", ""),
                    trade_in.get("serialNumber", ""),
                    trade_in.get("value", "")
                ))

            self.status_var.set(f"Loaded {len(trade_in_list)} trade-in items for quote {quote_id}.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load trade-ins: {str(e)}")
            self.status_var.set("Error loading trade-ins.")

    def trade_in_selected(self, event):
        """
        Handle trade-in selection event

        Args:
            event: The event that triggered this function
        """
        selected_item = self.trade_in_tree.selection()
        if not selected_item:
            return

        # Get the trade-in data from the selected item
        item_values = self.trade_in_tree.item(selected_item[0], "values")

        # Update the form fields
        self.trade_in_id_var.set(item_values[0])
        self.trade_in_model_var.set(item_values[1])
        self.trade_in_description_var.set(item_values[2])
        self.trade_in_serial_var.set(item_values[3])
        self.trade_in_value_var.set(item_values[4])

    def clear_trade_in_form(self):
        """
        Clear the trade-in form
        """
        self.trade_in_id_var.set("")
        self.trade_in_model_var.set("")
        self.trade_in_description_var.set("")
        self.trade_in_serial_var.set("")
        self.trade_in_value_var.set("0.00")

        # Clear the selection in the tree
        self.trade_in_tree.selection_remove(self.trade_in_tree.selection())

        self.status_var.set("Trade-in form cleared.")

    def add_trade_in(self):
        """
        Add trade-in to a quote
        """
        quote_id = self.trade_in_quote_id_var.get()
        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        try:
            self.status_var.set("Adding trade-in...")

            # Build trade-in data from form fields
            trade_in_data = {
                "tradeIn": {
                    "modelName": self.trade_in_model_var.get(),
                    "description": self.trade_in_description_var.get(),
                    "serialNumber": self.trade_in_serial_var.get(),
                    "value": float(self.trade_in_value_var.get())
                }
            }

            # Call the API to add trade-in
            result = self.maintain_quote_client.add_trade_in(quote_id, trade_in_data)

            # Check if the trade-in was added successfully
            if "body" in result:
                messagebox.showinfo("Success", "Trade-in added successfully.")

                # Reload the trade-in list
                self.load_trade_ins()

                # Clear the form
                self.clear_trade_in_form()

                self.status_var.set("Trade-in added.")
            else:
                messagebox.showwarning("Warning", "Trade-in addition response did not contain expected data.")
                self.status_var.set("Trade-in addition completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add trade-in: {str(e)}")
            self.status_var.set("Error adding trade-in.")

    def update_trade_in(self):
        """
        Update trade-in in a quote
        """
        quote_id = self.trade_in_quote_id_var.get()
        trade_in_id = self.trade_in_id_var.get()

        if not quote_id:
            messagebox.showinfo("Information", "Please enter a Quote ID.")
            return

        if not trade_in_id:
            messagebox.showinfo("Information", "Please select a trade-in item to update.")
            return

        try:
            self.status_var.set("Updating trade-in...")

            # Build trade-in data from form fields
            trade_in_data = {
                "tradeIn": {
                    "tradeInID": trade_in_id,
                    "modelName": self.trade_in_model_var.get(),
                    "description": self.trade_in_description_var.get(),
                    "serialNumber": self.trade_in_serial_var.get(),
                    "value": float(self.trade_in_value_var.get())
                }
            }

            # Call the API to update trade-in
            # Since there's no specific "update trade-in" endpoint, we'll use add_trade_in with the tradeInID set
            result = self.maintain_quote_client.add_trade_in(quote_id, trade_in_data)

            # Check if the trade-in was updated successfully
            if "body" in result:
                messagebox.showinfo("Success", "Trade-in updated successfully.")

                # Reload the trade-in list
                self.load_trade_ins()

                # Clear the form
                self.clear_trade_in_form()

                self.status_var.set("Trade-in updated.")
            else:
                messagebox.showwarning("Warning", "Trade-in update response did not contain expected data.")
                self.status_var.set("Trade-in update completed, but the response was unexpected.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update trade-in: {str(e)}")
            self.status_var.set("Error updating trade-in.")

    def setup_settings_tab(self):
        """
        Set up the settings tab
        """
        settings_frame = ttk.LabelFrame(self.settings_tab, text="API Configuration")
        settings_frame.pack(fill=tk.X, padx=10, pady=10)

        # Grid layout for settings
        row = 0

        # Client ID
        ttk.Label(settings_frame, text="Client ID:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.client_id_var = tk.StringVar(value=self.config.get("auth", "client_id", ""))
        ttk.Entry(settings_frame, textvariable=self.client_id_var, width=40).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # Client Secret
        ttk.Label(settings_frame, text="Client Secret:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.client_secret_var = tk.StringVar(value=self.config.get("auth", "client_secret", ""))
        secret_entry = ttk.Entry(settings_frame, textvariable=self.client_secret_var, width=40, show="•")
        secret_entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # Token URL
        ttk.Label(settings_frame, text="Token URL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.token_url_var = tk.StringVar(value=self.config.get("auth", "token_url", "https://signin.johndeere.com/oauth2/aus78tnlaysMraFhC1t7/v1/token"))
        ttk.Entry(settings_frame, textvariable=self.token_url_var, width=60).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # API Base URL
        ttk.Label(settings_frame, text="API Base URL:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.api_url_var = tk.StringVar(value=self.config.get("api", "quote_api_base_url", "https://jdquote2-api-sandbox.deere.com/om/cert/maintainquote"))
        ttk.Entry(settings_frame, textvariable=self.api_url_var, width=60).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # Dealer ID
        ttk.Label(settings_frame, text="Dealer ID:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.dealer_id_settings_var = tk.StringVar(value=self.config.get("api", "dealer_id", ""))
        ttk.Entry(settings_frame, textvariable=self.dealer_id_settings_var, width=20).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # Dealer Account Number
        ttk.Label(settings_frame, text="Dealer Account:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.dealer_account_settings_var = tk.StringVar(value=self.config.get("api", "dealer_account_number", ""))
        ttk.Entry(settings_frame, textvariable=self.dealer_account_settings_var, width=20).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        row += 1

        # Environment selection (sandbox/production)
        ttk.Label(settings_frame, text="Environment:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.environment_var = tk.StringVar(value="sandbox")
        environment_frame = ttk.Frame(settings_frame)
        environment_frame.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Radiobutton(environment_frame, text="Sandbox", variable=self.environment_var, value="sandbox").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(environment_frame, text="Production", variable=self.environment_var, value="production").pack(side=tk.LEFT, padx=5)
        row += 1

        # Save button
        self.save_button = ttk.Button(settings_frame, text="Save Settings", command=self.save_settings)
        self.save_button.grid(row=row, column=1, sticky=tk.E, padx=5, pady=10)

        # Test connection button
        self.test_button = ttk.Button(settings_frame, text="Test Connection", command=self.test_connection)
        self.test_button.grid(row=row, column=0, sticky=tk.W, padx=5, pady=10)

        # Add API Documentation section
        docs_frame = ttk.LabelFrame(self.settings_tab, text="API Documentation")
        docs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Add some basic documentation text
        docs_text = tk.Text(docs_frame, wrap=tk.WORD, height=15)
        docs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(docs_frame, orient=tk.VERTICAL, command=docs_text.yview)
        docs_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert documentation
        docs_text.insert(tk.END, """The John Deere Maintain Quote API allows you to create, manipulate, and fetch Quote related data.

Key Endpoints:
- POST /api/v1/maintain-quotes - Create a new quote
- POST /api/v1/quotes/{quoteId}/equipments - Add equipment to a quote
- POST /api/v1/quotes/{quoteId}/master-quotes - Add a master quote
- POST /api/v1/quotes/{quoteId}/copy-quote - Copy a quote
- DELETE /api/v1/quotes/{quoteId}/equipments - Delete equipment from a quote
- GET /api/v1/quotes/{quoteId}/maintain-quote-details - Get quote details
- POST /api/v1/dealers/{dealerId}/quotes - Create a dealer quote
- POST /api/v1/quotes/{quoteId}/expiration-date - Update expiration date
- POST /api/v1/dealers/{dealerRacfId}/maintain-quotes - Create a dealer maintain quote
- PUT /api/v1/quotes/{quoteId}/maintain-quotes - Update a quote
- POST /api/v1/quotes/{quoteId}/save-quotes - Save a quote
- POST /api/v1/quotes/{quoteId}/trade-in - Add trade-in information
- DELETE /api/v1/quotes/{quoteId}/dealers/{dealerId} - Delete a quote

For more information, please refer to the John Deere Developer documentation.
""")

        # Make the text read-only
        docs_text.configure(state="disabled")

    def save_settings(self):
        """
        Save settings to the configuration file
        """
        try:
            # Update configuration
            self.config.set("auth", "client_id", self.client_id_var.get())
            self.config.set("auth", "client_secret", self.client_secret_var.get())
            self.config.set("auth", "token_url", self.token_url_var.get())

            # Set API URL based on environment
            base_url = self.api_url_var.get()
            if self.environment_var.get() == "production":
                # Replace sandbox with production
                base_url = base_url.replace("sandbox", "")
                base_url = base_url.replace("cert/", "")

            self.config.set("api", "quote_api_base_url", base_url)
            self.config.set("api", "dealer_id", self.dealer_id_settings_var.get())
            self.config.set("api", "dealer_account_number", self.dealer_account_settings_var.get())

            # Update the dealer account and ID in the create tab
            self.dealer_id_var.set(self.dealer_id_settings_var.get())
            self.dealer_account_var.set(self.dealer_account_settings_var.get())

            messagebox.showinfo("Success", "Settings saved successfully.")
            self.status_var.set("Settings saved.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
            self.status_var.set("Error saving settings.")

    def test_connection(self):
        """
        Test the connection to the API
        """
        try:
            # Update configuration with current values
            self.config.set("auth", "client_id", self.client_id_var.get())
            self.config.set("auth", "client_secret", self.client_secret_var.get())
            self.config.set("auth", "token_url", self.token_url_var.get())

            # Set API URL based on environment
            base_url = self.api_url_var.get()
            if self.environment_var.get() == "production":
                # Replace sandbox with production
                base_url = base_url.replace("sandbox", "")
                base_url = base_url.replace("cert/", "")

            self.config.set("api", "quote_api_base_url", base_url)

            # Import here to avoid circular imports
            from auth.oauth import JDOAuthClient
            from api.maintain_quote_client import MaintainQuoteClient

            # Create a new OAuth client with the current settings
            oauth_client = JDOAuthClient(
                self.client_id_var.get(),
                self.client_secret_var.get(),
                self.token_url_var.get()
            )

            # Try to get a token
            token = oauth_client.get_token()

            # Create a new Maintain Quote client with the OAuth client
            maintain_quote_client = MaintainQuoteClient(oauth_client, base_url)

            # Try a simple API request
            # Note: We can't easily make a "safe" test request without knowing a valid quote ID,
            # so we'll just verify that we got a token

            messagebox.showinfo("Success", "Connection test successful. Obtained OAuth token.")
            self.status_var.set("Connection test successful.")

        except Exception as e:
            messagebox.showerror("Error", f"Connection test failed: {str(e)}")
            self.status_var.set("Connection test failed.")