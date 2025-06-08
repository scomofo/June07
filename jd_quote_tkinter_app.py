#!/usr/bin/env python3
"""
John Deere Quote Tkinter Application
------------------------------------
This application provides a standalone interface for creating and editing
John Deere quotes. It receives input data from the main application and
returns quote information when complete.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import sys
import os
import argparse
from datetime import datetime
import uuid

class JDQuoteApp:
    def __init__(self, root, input_data=None):
        self.root = root
        self.root.title("John Deere Quote Tool")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # Set icon if available
        try:
            self.root.iconbitmap("resources/icons/jd_icon.ico")
        except:
            pass  # Ignore if icon not available
            
        # Default quote data
        self.quote_data = {
            "quoteID": str(uuid.uuid4())[:8],
            "creationDate": datetime.now().strftime("%Y-%m-%d"),
            "customerData": {},
            "equipmentData": [],
            "tradeInEquipmentData": [],
            "custNotes": "",
            "salesPerson": "",
            "expirationDate": "",
            "quoteStatusId": 1,
            "totalEquipmentCost": 0.0,
            "totalNetTradeValue": 0.0
        }
        
        # Load input data if provided
        if input_data:
            self.merge_input_data(input_data)
            
        self.create_ui()
        self.load_data_to_ui()
        
        # When window closes, output the data
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def merge_input_data(self, input_data):
        """Merge input data with default quote structure"""
        # Customer data
        if "customer_name" in input_data:
            customer_name = input_data["customer_name"].split()
            self.quote_data["customerData"]["customerFirstName"] = customer_name[0] if customer_name else ""
            self.quote_data["customerData"]["customerLastName"] = " ".join(customer_name[1:]) if len(customer_name) > 1 else ""
            
        # Copy other customer fields if present
        customer_fields = ["customerEmail", "customerPhone", "customerAddr1", "customerCity", 
                          "customerState", "customerZipCode", "customerCountry"]
        for field in customer_fields:
            if field in input_data:
                self.quote_data["customerData"][field] = input_data[field]
                
        # Equipment data
        if "equipment_items" in input_data and isinstance(input_data["equipment_items"], list):
            for item in input_data["equipment_items"]:
                equipment = {
                    "dealerSpecifiedModel": item.get("name", ""),
                    "dealerStockNumber": item.get("stock_number", ""),
                    "dealerOrderNumber": item.get("order_number", ""),
                    "listPrice": float(item.get("price", 0)),
                    "costPrice": float(item.get("price", 0)) * 0.9,  # Estimate cost as 90% of price
                    "serialNo": item.get("serial_number", ""),
                    "makeID": 1,  # Default to John Deere
                    "categoryID": 1012,  # Default category
                    "equipmentID": str(uuid.uuid4())[:8]
                }
                self.quote_data["equipmentData"].append(equipment)
                
        # Trade-in data
        if "trade_items" in input_data and isinstance(input_data["trade_items"], list):
            for item in input_data["trade_items"]:
                trade = {
                    "dealerSpecifiedModel": item.get("name", ""),
                    "serialNo": "",
                    "netTradeValue": float(item.get("amount", 0)),
                    "makeID": 1,  # Default to John Deere
                    "tradeInID": str(uuid.uuid4())[:8]
                }
                self.quote_data["tradeInEquipmentData"].append(trade)
                
        # Notes
        if "deal_notes" in input_data:
            self.quote_data["custNotes"] = input_data["deal_notes"]
            
        # Salesperson
        if "salesperson" in input_data:
            self.quote_data["salesPerson"] = input_data["salesperson"]
            
        # Set expiration date to 30 days from now
        self.quote_data["expirationDate"] = (datetime.now().replace(day=1) + 
                                           datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        
        # Calculate totals
        self._update_totals()
        
    def _update_totals(self):
        """Update total costs and values"""
        self.quote_data["totalEquipmentCost"] = sum(eq.get("listPrice", 0) for eq in self.quote_data["equipmentData"])
        self.quote_data["totalNetTradeValue"] = sum(tr.get("netTradeValue", 0) for tr in self.quote_data["tradeInEquipmentData"])
    
    def create_ui(self):
        """Create the user interface"""
        # Create a main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create tab frames
        self.quote_info_frame = ttk.Frame(notebook, padding=10)
        self.equipment_frame = ttk.Frame(notebook, padding=10)
        self.trades_frame = ttk.Frame(notebook, padding=10)
        self.notes_frame = ttk.Frame(notebook, padding=10)
        
        # Add tabs to notebook
        notebook.add(self.quote_info_frame, text="Quote Information")
        notebook.add(self.equipment_frame, text="Equipment")
        notebook.add(self.trades_frame, text="Trade-Ins")
        notebook.add(self.notes_frame, text="Notes")
        
        # Setup each tab
        self._setup_quote_info_tab()
        self._setup_equipment_tab()
        self._setup_trades_tab()
        self._setup_notes_tab()
        
        # Bottom buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # Add Save and Cancel buttons
        save_btn = ttk.Button(button_frame, text="Save Quote", command=self.on_save)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="Cancel", command=self.on_cancel)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def _setup_quote_info_tab(self):
        """Setup the Quote Information tab"""
        # Create frames for organization
        left_frame = ttk.Frame(self.quote_info_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(self.quote_info_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Quote details - left frame
        quote_group = ttk.LabelFrame(left_frame, text="Quote Details")
        quote_group.pack(fill=tk.X, pady=5)
        
        # Quote ID
        ttk.Label(quote_group, text="Quote ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.quote_id_var = tk.StringVar()
        ttk.Entry(quote_group, textvariable=self.quote_id_var, state="readonly").grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Creation Date
        ttk.Label(quote_group, text="Creation Date:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.creation_date_var = tk.StringVar()
        ttk.Entry(quote_group, textvariable=self.creation_date_var).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Expiration Date
        ttk.Label(quote_group, text="Expiration Date:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.expiration_date_var = tk.StringVar()
        ttk.Entry(quote_group, textvariable=self.expiration_date_var).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Sales Person
        ttk.Label(quote_group, text="Sales Person:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.salesperson_var = tk.StringVar()
        ttk.Entry(quote_group, textvariable=self.salesperson_var).grid(row=3, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Status
        ttk.Label(quote_group, text="Status:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.status_options = ["Draft", "Submitted", "Approved", "Expired", "Rejected"]
        self.status_var = tk.StringVar()
        ttk.Combobox(quote_group, textvariable=self.status_var, values=self.status_options).grid(
            row=4, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Totals
        totals_group = ttk.LabelFrame(left_frame, text="Totals")
        totals_group.pack(fill=tk.X, pady=5)
        
        ttk.Label(totals_group, text="Equipment Total:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.equipment_total_var = tk.StringVar()
        ttk.Entry(totals_group, textvariable=self.equipment_total_var, state="readonly").grid(
            row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        ttk.Label(totals_group, text="Trade-In Total:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.tradein_total_var = tk.StringVar()
        ttk.Entry(totals_group, textvariable=self.tradein_total_var, state="readonly").grid(
            row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        ttk.Label(totals_group, text="Balance:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.balance_var = tk.StringVar()
        ttk.Entry(totals_group, textvariable=self.balance_var, state="readonly").grid(
            row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Customer information - right frame
        customer_group = ttk.LabelFrame(right_frame, text="Customer Information")
        customer_group.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # First Name
        ttk.Label(customer_group, text="First Name:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.first_name_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.first_name_var).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Last Name
        ttk.Label(customer_group, text="Last Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.last_name_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.last_name_var).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Email
        ttk.Label(customer_group, text="Email:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.email_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.email_var).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Phone
        ttk.Label(customer_group, text="Phone:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.phone_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.phone_var).grid(row=3, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Address 1
        ttk.Label(customer_group, text="Address:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.address_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.address_var).grid(row=4, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # City
        ttk.Label(customer_group, text="City:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.city_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.city_var).grid(row=5, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # State
        ttk.Label(customer_group, text="State:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        self.state_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.state_var).grid(row=6, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Zip Code
        ttk.Label(customer_group, text="Zip Code:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=2)
        self.zip_var = tk.StringVar()
        ttk.Entry(customer_group, textvariable=self.zip_var).grid(row=7, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Country
        ttk.Label(customer_group, text="Country:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=2)
        self.country_var = tk.StringVar()
        self.country_var.set("US")
        ttk.Entry(customer_group, textvariable=self.country_var).grid(row=8, column=1, sticky=tk.W+tk.E, padx=5, pady=2)
        
        # Configure grid columns to expand
        for frame in [quote_group, totals_group, customer_group]:
            frame.columnconfigure(1, weight=1)
    
    def _setup_equipment_tab(self):
        """Setup the Equipment tab"""
        # Buttons for equipment actions
        btn_frame = ttk.Frame(self.equipment_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        
        add_btn = ttk.Button(btn_frame, text="Add Equipment", command=self.add_equipment)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        edit_btn = ttk.Button(btn_frame, text="Edit Selected", command=self.edit_equipment)
        edit_btn.pack(side=tk.LEFT, padx=5)
        
        delete_btn = ttk.Button(btn_frame, text="Delete Selected", command=self.delete_equipment)
        delete_btn.pack(side=tk.LEFT, padx=5)
        
        # Equipment table
        columns = ("model", "stock", "order_number", "serial", "price")
        self.equipment_tree = ttk.Treeview(self.equipment_frame, columns=columns, show="headings")
        
        # Define headings
        self.equipment_tree.heading("model", text="Model")
        self.equipment_tree.heading("stock", text="Stock #")
        self.equipment_tree.heading("order_number", text="Order #")
        self.equipment_tree.heading("serial", text="Serial #")
        self.equipment_tree.heading("price", text="Price")
        
        # Define columns
        self.equipment_tree.column("model", width=250)
        self.equipment_tree.column("stock", width=100)
        self.equipment_tree.column("order_number", width=100)
        self.equipment_tree.column("serial", width=150)
        self.equipment_tree.column("price", width=100)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.equipment_frame, orient=tk.VERTICAL, command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscroll=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.equipment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_trades_tab(self):
        """Setup the Trade-Ins tab"""
        # Buttons for trade-in actions
        btn_frame = ttk.Frame(self.trades_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))
        
        add_btn = ttk.Button(btn_frame, text="Add Trade-In", command=self.add_trade)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        edit_btn = ttk.Button(btn_frame, text="Edit Selected", command=self.edit_trade)
        edit_btn.pack(side=tk.LEFT, padx=5)
        
        delete_btn = ttk.Button(btn_frame, text="Delete Selected", command=self.delete_trade)
        delete_btn.pack(side=tk.LEFT, padx=5)
        
        # Trade-in table
        columns = ("model", "serial", "value")
        self.trades_tree = ttk.Treeview(self.trades_frame, columns=columns, show="headings")
        
        # Define headings
        self.trades_tree.heading("model", text="Model")
        self.trades_tree.heading("serial", text="Serial #")
        self.trades_tree.heading("value", text="Value")
        
        # Define columns
        self.trades_tree.column("model", width=300)
        self.trades_tree.column("serial", width=150)
        self.trades_tree.column("value", width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.trades_frame, orient=tk.VERTICAL, command=self.trades_tree.yview)
        self.trades_tree.configure(yscroll=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.trades_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_notes_tab(self):
        """Setup the Notes tab"""
        notes_label = ttk.Label(self.notes_frame, text="Quote Notes:")
        notes_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.notes_text = scrolledtext.ScrolledText(self.notes_frame, height=15)
        self.notes_text.pack(fill=tk.BOTH, expand=True)
    
    def load_data_to_ui(self):
        """Load data from the quote_data object to the UI elements"""
        # Quote info
        self.quote_id_var.set(self.quote_data.get("quoteID", ""))
        self.creation_date_var.set(self.quote_data.get("creationDate", ""))
        self.expiration_date_var.set(self.quote_data.get("expirationDate", ""))
        self.salesperson_var.set(self.quote_data.get("salesPerson", ""))
        
        status_id = self.quote_data.get("quoteStatusId", 1)
        if 1 <= status_id <= len(self.status_options):
            self.status_var.set(self.status_options[status_id-1])
        else:
            self.status_var.set(self.status_options[0])
        
        # Totals
        equipment_total = self.quote_data.get("totalEquipmentCost", 0)
        tradein_total = self.quote_data.get("totalNetTradeValue", 0)
        balance = equipment_total - tradein_total
        
        self.equipment_total_var.set(f"${equipment_total:,.2f}")
        self.tradein_total_var.set(f"${tradein_total:,.2f}")
        self.balance_var.set(f"${balance:,.2f}")
        
        # Customer info
        customer_data = self.quote_data.get("customerData", {})
        self.first_name_var.set(customer_data.get("customerFirstName", ""))
        self.last_name_var.set(customer_data.get("customerLastName", ""))
        self.email_var.set(customer_data.get("customerEmail", ""))
        self.phone_var.set(customer_data.get("customerPhone", ""))
        self.address_var.set(customer_data.get("customerAddr1", ""))
        self.city_var.set(customer_data.get("customerCity", ""))
        self.state_var.set(customer_data.get("customerState", ""))
        self.zip_var.set(customer_data.get("customerZipCode", ""))
        self.country_var.set(customer_data.get("customerCountry", "US"))
        
        # Equipment
        self.equipment_tree.delete(*self.equipment_tree.get_children())
        for equipment in self.quote_data.get("equipmentData", []):
            self.equipment_tree.insert("", "end", 
                values=(
                    equipment.get("dealerSpecifiedModel", ""),
                    equipment.get("dealerStockNumber", ""),
                    equipment.get("dealerOrderNumber", ""),
                    equipment.get("serialNo", ""),
                    f"${equipment.get('listPrice', 0):,.2f}"
                ),
                tags=(equipment.get("equipmentID", ""),)
            )
        
        # Trade-ins
        self.trades_tree.delete(*self.trades_tree.get_children())
        for trade in self.quote_data.get("tradeInEquipmentData", []):
            self.trades_tree.insert("", "end", 
                values=(
                    trade.get("dealerSpecifiedModel", ""),
                    trade.get("serialNo", ""),
                    f"${trade.get('netTradeValue', 0):,.2f}"
                ),
                tags=(trade.get("tradeInID", ""),)
            )
        
        # Notes
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(tk.END, self.quote_data.get("custNotes", ""))
    
    def update_data_from_ui(self):
        """Update the quote_data object from UI elements"""
        # Quote info
        self.quote_data["creationDate"] = self.creation_date_var.get()
        self.quote_data["expirationDate"] = self.expiration_date_var.get()
        self.quote_data["salesPerson"] = self.salesperson_var.get()
        
        status_text = self.status_var.get()
        if status_text in self.status_options:
            self.quote_data["quoteStatusId"] = self.status_options.index(status_text) + 1
        
        # Customer info
        if "customerData" not in self.quote_data:
            self.quote_data["customerData"] = {}
            
        self.quote_data["customerData"]["customerFirstName"] = self.first_name_var.get()
        self.quote_data["customerData"]["customerLastName"] = self.last_name_var.get()
        self.quote_data["customerData"]["customerEmail"] = self.email_var.get()
        self.quote_data["customerData"]["customerPhone"] = self.phone_var.get()
        self.quote_data["customerData"]["customerAddr1"] = self.address_var.get()
        self.quote_data["customerData"]["customerCity"] = self.city_var.get()
        self.quote_data["customerData"]["customerState"] = self.state_var.get()
        self.quote_data["customerData"]["customerZipCode"] = self.zip_var.get()
        self.quote_data["customerData"]["customerCountry"] = self.country_var.get()
        
        # Notes
        self.quote_data["custNotes"] = self.notes_text.get(1.0, tk.END).strip()
        
        # Equipment and trade-ins are updated via their respective dialogs
        
        # Update totals
        self._update_totals()
    
    def add_equipment(self):
        """Open dialog to add new equipment"""
        dialog = EquipmentDialog(self.root, title="Add Equipment")
        if dialog.result:
            equipment_id = str(uuid.uuid4())[:8]
            equipment = {
                "dealerSpecifiedModel": dialog.result["model"],
                "dealerStockNumber": dialog.result["stock"],
                "dealerOrderNumber": dialog.result["order"],
                "serialNo": dialog.result["serial"],
                "listPrice": float(dialog.result["price"]),
                "costPrice": float(dialog.result["price"]) * 0.9,  # Estimate cost as 90% of price
                "makeID": 1,  # Default to John Deere
                "categoryID": 1012,  # Default category
                "equipmentID": equipment_id
            }
            
            # Add to data model
            self.quote_data["equipmentData"].append(equipment)
            
            # Add to treeview
            self.equipment_tree.insert("", "end", 
                values=(
                    equipment["dealerSpecifiedModel"],
                    equipment["dealerStockNumber"],
                    equipment["dealerOrderNumber"],
                    equipment["serialNo"],
                    f"${equipment['listPrice']:,.2f}"
                ),
                tags=(equipment_id,)
            )
            
            # Update totals
            self._update_totals()
            self.equipment_total_var.set(f"${self.quote_data['totalEquipmentCost']:,.2f}")
            balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
            self.balance_var.set(f"${balance:,.2f}")
            
            self.status_var.set(f"Added equipment: {equipment['dealerSpecifiedModel']}")
    
    def edit_equipment(self):
        """Edit selected equipment"""
        selected = self.equipment_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select an equipment item to edit.")
            return
        
        selected_id = self.equipment_tree.item(selected[0], "tags")[0]
        
        # Find equipment in data
        equipment = None
        for eq in self.quote_data["equipmentData"]:
            if eq.get("equipmentID") == selected_id:
                equipment = eq
                break
                
        if not equipment:
            messagebox.showerror("Error", "Could not find equipment data.")
            return
            
        # Open dialog with current values
        dialog = EquipmentDialog(
            self.root, 
            title="Edit Equipment",
            model=equipment.get("dealerSpecifiedModel", ""),
            stock=equipment.get("dealerStockNumber", ""),
            order=equipment.get("dealerOrderNumber", ""),
            serial=equipment.get("serialNo", ""),
            price=equipment.get("listPrice", 0)
        )
        
        if dialog.result:
            # Update data model
            equipment["dealerSpecifiedModel"] = dialog.result["model"]
            equipment["dealerStockNumber"] = dialog.result["stock"]
            equipment["dealerOrderNumber"] = dialog.result["order"]
            equipment["serialNo"] = dialog.result["serial"]
            equipment["listPrice"] = float(dialog.result["price"])
            equipment["costPrice"] = float(dialog.result["price"]) * 0.9  # Update cost
            
            # Update treeview
            self.equipment_tree.item(selected[0], values=(
                equipment["dealerSpecifiedModel"],
                equipment["dealerStockNumber"],
                equipment["dealerOrderNumber"],
                equipment["serialNo"],
                f"${equipment['listPrice']:,.2f}"
            ))
            
            # Update totals
            self._update_totals()
            self.equipment_total_var.set(f"${self.quote_data['totalEquipmentCost']:,.2f}")
            balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
            self.balance_var.set(f"${balance:,.2f}")
            
            self.status_var.set(f"Updated equipment: {equipment['dealerSpecifiedModel']}")
    
    def delete_equipment(self):
        """Delete selected equipment"""
        selected = self.equipment_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select an equipment item to delete.")
            return
        
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected equipment?"):
            return
            
        selected_id = self.equipment_tree.item(selected[0], "tags")[0]
        
        # Remove from data model
        for i, eq in enumerate(self.quote_data["equipmentData"]):
            if eq.get("equipmentID") == selected_id:
                model_name = eq.get("dealerSpecifiedModel", "")
                del self.quote_data["equipmentData"][i]
                break
        
        # Remove from treeview
        self.equipment_tree.delete(selected[0])
        
        # Update totals
        self._update_totals()
        self.equipment_total_var.set(f"${self.quote_data['totalEquipmentCost']:,.2f}")
        balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
        self.balance_var.set(f"${balance:,.2f}")
        
        self.status_var.set(f"Deleted equipment: {model_name}")
    
    def add_trade(self):
        """Open dialog to add new trade-in"""
        dialog = TradeInDialog(self.root, title="Add Trade-In")
        if dialog.result:
            trade_id = str(uuid.uuid4())[:8]
            trade = {
                "dealerSpecifiedModel": dialog.result["model"],
                "serialNo": dialog.result["serial"],
                "netTradeValue": float(dialog.result["value"]),
                "makeID": 1,  # Default to John Deere
                "tradeInID": trade_id
            }
            
            # Add to data model
            self.quote_data["tradeInEquipmentData"].append(trade)
            
            # Add to treeview
            self.trades_tree.insert("", "end", 
                values=(
                    trade["dealerSpecifiedModel"],
                    trade["serialNo"],
                    f"${trade['netTradeValue']:,.2f}"
                ),
                tags=(trade_id,)
            )
            
            # Update totals
            self._update_totals()
            self.tradein_total_var.set(f"${self.quote_data['totalNetTradeValue']:,.2f}")
            balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
            self.balance_var.set(f"${balance:,.2f}")
            
            self.status_var.set(f"Added trade-in: {trade['dealerSpecifiedModel']}")
    
    def edit_trade(self):
        """Edit selected trade-in"""
        selected = self.trades_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a trade-in item to edit.")
            return
        
        selected_id = self.trades_tree.item(selected[0], "tags")[0]
        
        # Find trade-in in data
        trade = None
        for tr in self.quote_data["tradeInEquipmentData"]:
            if tr.get("tradeInID") == selected_id:
                trade = tr
                break
                
        if not trade:
            messagebox.showerror("Error", "Could not find trade-in data.")
            return
            
        # Open dialog with current values
        dialog = TradeInDialog(
            self.root, 
            title="Edit Trade-In",
            model=trade.get("dealerSpecifiedModel", ""),
            serial=trade.get("serialNo", ""),
            value=trade.get("netTradeValue", 0)
        )
        
        if dialog.result:
            # Update data model
            trade["dealerSpecifiedModel"] = dialog.result["model"]
            trade["serialNo"] = dialog.result["serial"]
            trade["netTradeValue"] = float(dialog.result["value"])
            
            # Update treeview
            self.trades_tree.item(selected[0], values=(
                trade["dealerSpecifiedModel"],
                trade["serialNo"],
                f"${trade['netTradeValue']:,.2f}"
            ))
            
            # Update totals
            self._update_totals()
            self.tradein_total_var.set(f"${self.quote_data['totalNetTradeValue']:,.2f}")
            balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
            self.balance_var.set(f"${balance:,.2f}")
            
            self.status_var.set(f"Updated trade-in: {trade['dealerSpecifiedModel']}")
    
    def delete_trade(self):
        """Delete selected trade-in"""
        selected = self.trades_tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a trade-in item to delete.")
            return
        
        if not messagebox.askyesno("Confirm Delete", "Are you sure you want to delete the selected trade-in?"):
            return
            
        selected_id = self.trades_tree.item(selected[0], "tags")[0]
        
        # Remove from data model
        for i, tr in enumerate(self.quote_data["tradeInEquipmentData"]):
            if tr.get("tradeInID") == selected_id:
                model_name = tr.get("dealerSpecifiedModel", "")
                del self.quote_data["tradeInEquipmentData"][i]
                break
        
        # Remove from treeview
        self.trades_tree.delete(selected[0])
        
        # Update totals
        self._update_totals()
        self.tradein_total_var.set(f"${self.quote_data['totalNetTradeValue']:,.2f}")
        balance = self.quote_data["totalEquipmentCost"] - self.quote_data["totalNetTradeValue"]
        self.balance_var.set(f"${balance:,.2f}")
        
        self.status_var.set(f"Deleted trade-in: {model_name}")
    
    def on_save(self):
        """Save the quote and output it"""
        # Update data from UI
        self.update_data_from_ui()
        
        # Validate required fields
        if not self.validate_quote():
            return
            
        # Get confirmation
        if messagebox.askyesno("Save Quote", "Save this quote and close the application?"):
            # Return data to caller application
            self.on_close(save=True)
    
    def validate_quote(self):
        """Validate the quote data before saving"""
        # Check customer info
        if not self.first_name_var.get() or not self.last_name_var.get():
            messagebox.showwarning("Validation Error", "Customer first and last name are required.")
            return False
            
        # Check if any equipment is added
        if not self.quote_data["equipmentData"]:
            messagebox.showwarning("Validation Error", "At least one equipment item is required.")
            return False
            
        return True
    
    def on_cancel(self):
        """Cancel and close without saving"""
        if messagebox.askyesno("Cancel", "Are you sure you want to cancel? Any changes will be lost."):
            self.root.destroy()
    
    def on_close(self, save=False):
        """Handle window close event"""
        if save:
            # Update data from UI one last time
            self.update_data_from_ui()
            
            # Output to stdout for parent application
            result = {
                "status": "success",
                "quote_id": self.quote_data["quoteID"],
                "customer_name": f"{self.quote_data['customerData'].get('customerFirstName', '')} {self.quote_data['customerData'].get('customerLastName', '')}".strip(),
                "quote_data": self.quote_data
            }
            print(json.dumps(result))
            
        self.root.destroy()


class EquipmentDialog:
    """Dialog for adding or editing equipment"""
    def __init__(self, parent, title="Equipment", model="", stock="", order="", serial="", price=0):
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create form
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Model
        ttk.Label(frame, text="Model:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value=model)
        ttk.Entry(frame, textvariable=self.model_var, width=30).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Stock Number
        ttk.Label(frame, text="Stock #:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.stock_var = tk.StringVar(value=stock)
        ttk.Entry(frame, textvariable=self.stock_var, width=30).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Order Number
        ttk.Label(frame, text="Order #:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.order_var = tk.StringVar(value=order)
        ttk.Entry(frame, textvariable=self.order_var, width=30).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Serial Number
        ttk.Label(frame, text="Serial #:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.serial_var = tk.StringVar(value=serial)
        ttk.Entry(frame, textvariable=self.serial_var, width=30).grid(row=3, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Price
        ttk.Label(frame, text="Price:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.price_var = tk.StringVar(value=str(price))
        ttk.Entry(frame, textvariable=self.price_var, width=30).grid(row=4, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid
        frame.columnconfigure(1, weight=1)
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def on_ok(self):
        """Validate and save the equipment data"""
        # Validate
        if not self.model_var.get():
            messagebox.showwarning("Validation Error", "Equipment model is required.", parent=self.dialog)
            return
            
        try:
            price = float(self.price_var.get().replace('$', '').replace(',', ''))
            if price < 0:
                raise ValueError("Price must be positive")
        except ValueError:
            messagebox.showwarning("Validation Error", "Price must be a valid number.", parent=self.dialog)
            return
            
        # Save result
        self.result = {
            "model": self.model_var.get(),
            "stock": self.stock_var.get(),
            "order": self.order_var.get(),
            "serial": self.serial_var.get(),
            "price": price
        }
        
        # Close dialog
        self.dialog.destroy()


class TradeInDialog:
    """Dialog for adding or editing trade-in"""
    def __init__(self, parent, title="Trade-In", model="", serial="", value=0):
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create form
        frame = ttk.Frame(self.dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Model
        ttk.Label(frame, text="Model:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar(value=model)
        ttk.Entry(frame, textvariable=self.model_var, width=30).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Serial Number
        ttk.Label(frame, text="Serial #:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.serial_var = tk.StringVar(value=serial)
        ttk.Entry(frame, textvariable=self.serial_var, width=30).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Value
        ttk.Label(frame, text="Value:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.value_var = tk.StringVar(value=str(value))
        ttk.Entry(frame, textvariable=self.value_var, width=30).grid(row=2, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Configure grid
        frame.columnconfigure(1, weight=1)
        
        # Wait for dialog to close
        self.dialog.wait_window()
    
    def on_ok(self):
        """Validate and save the trade-in data"""
        # Validate
        if not self.model_var.get():
            messagebox.showwarning("Validation Error", "Trade-in model is required.", parent=self.dialog)
            return
            
        try:
            value = float(self.value_var.get().replace('$', '').replace(',', ''))
            if value < 0:
                raise ValueError("Value must be positive")
        except ValueError:
            messagebox.showwarning("Validation Error", "Value must be a valid number.", parent=self.dialog)
            return
            
        # Save result
        self.result = {
            "model": self.model_var.get(),
            "serial": self.serial_var.get(),
            "value": value
        }
        
        # Close dialog
        self.dialog.destroy()


def load_input_data(input_file_path):
    """Load input data from a JSON file"""
    if not input_file_path or not os.path.exists(input_file_path):
        print(f"Input file not found: {input_file_path}")
        return None
        
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        print(f"Successfully loaded input data from {input_file_path}")
        return input_data
    except Exception as e:
        print(f"Error loading input data: {e}")
        return None


def main():
    """Main entry point for the application"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='John Deere Quote Tkinter Application')
    parser.add_argument('--input-file', help='Path to JSON input file with quote data')
    args = parser.parse_args()
    
    # Load input data if provided
    input_data = None
    if args.input_file:
        input_data = load_input_data(args.input_file)
    
    # Create Tkinter application
    root = tk.Tk()
    app = JDQuoteApp(root, input_data)
    root.mainloop()


if __name__ == "__main__":
    main()