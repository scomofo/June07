import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import shutil

TARGET_ICON_NAMES = [
    "app_icon.png",
    "calculator.png",
    "customers.png",
    "data_editors_icon.png",
    "invoice_icon.png",
    "jd_quote_icon.png",
    "logo.png",
    "new_deal_icon.png",
    "parts_icon.png",
    "price_book_icon.png",
    "receiving_icon.png",
    "recent_deals_icon.png",
    "splash_main.png",
    "used_inventory_icon.png",
    "my_icon.png",
    "another_icon.png",
    "default_icon.png",
    "another_default.png"
]

IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg']

class BatchRenamerApp:
    def __init__(self, master):
        self.master = master
        master.title("Batch Image Renamer")
        master.geometry("950x600")

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.staged_renames = {}  # {current_filename: target_filename}

        # --- Main Frames ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        list_area_frame = ttk.Frame(main_frame)
        list_area_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP, pady=10)

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)

        # --- Column 1: Target Filenames ---
        target_frame = ttk.LabelFrame(list_area_frame, text="Target Filenames", padding="10")
        target_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.target_listbox = tk.Listbox(target_frame, exportselection=False, width=30)
        self.target_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        target_scrollbar = ttk.Scrollbar(target_frame, orient=tk.VERTICAL, command=self.target_listbox.yview)
        target_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.target_listbox.config(yscrollcommand=target_scrollbar.set)
        for name in sorted(TARGET_ICON_NAMES):
            self.target_listbox.insert(tk.END, name)

        # --- Column 2: Current Image Files ---
        current_frame = ttk.LabelFrame(list_area_frame, text="Current Image Files in Script Directory", padding="10")
        current_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.current_files_listbox = tk.Listbox(current_frame, exportselection=False, width=40)
        self.current_files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        current_scrollbar = ttk.Scrollbar(current_frame, orient=tk.VERTICAL, command=self.current_files_listbox.yview)
        current_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.current_files_listbox.config(yscrollcommand=current_scrollbar.set)
        
        # --- Column 3: Staged Renames ---
        staged_frame = ttk.LabelFrame(list_area_frame, text="Staged Renames (Current -> Target)", padding="10")
        staged_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.staged_listbox = tk.Listbox(staged_frame, exportselection=False, width=50)
        self.staged_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        staged_scrollbar = ttk.Scrollbar(staged_frame, orient=tk.VERTICAL, command=self.staged_listbox.yview)
        staged_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.staged_listbox.config(yscrollcommand=staged_scrollbar.set)

        # --- Control Buttons ---
        # Frame for staging controls
        staging_controls_frame = ttk.Frame(controls_frame)
        staging_controls_frame.pack(fill=tk.X, pady=(0,10))

        self.refresh_button = ttk.Button(staging_controls_frame, text="Refresh Current Files", command=self.populate_current_files)
        self.refresh_button.pack(side=tk.LEFT, padx=5)

        self.stage_button = ttk.Button(staging_controls_frame, text="Stage Rename >>", command=self.stage_rename)
        self.stage_button.pack(side=tk.LEFT, padx=5)
        
        self.unstage_button = ttk.Button(staging_controls_frame, text="Unstage Selected", command=self.unstage_rename)
        self.unstage_button.pack(side=tk.LEFT, padx=5)

        # Frame for process controls
        process_controls_frame = ttk.Frame(controls_frame)
        process_controls_frame.pack(fill=tk.X)

        self.process_button = ttk.Button(process_controls_frame, text="Process Renames", command=self.process_renames_confirmation, style="Accent.TButton")
        self.process_button.pack(side=tk.RIGHT, padx=5)
        
        # Status Bar
        self.status_bar = ttk.Label(master, text="Ready. Select files to stage for renaming.", relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Styling for Accent Button
        style = ttk.Style()
        style.configure("Accent.TButton", font=('Helvetica', 10, 'bold'), background="green")


        self.populate_current_files()

    def update_status(self, message):
        self.status_bar.config(text=message)
        self.master.update_idletasks()

    def populate_current_files(self):
        self.current_files_listbox.delete(0, tk.END)
        try:
            files = [f for f in os.listdir(self.script_dir)
                     if os.path.isfile(os.path.join(self.script_dir, f)) and
                        os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS]
            for f_name in sorted(files):
                self.current_files_listbox.insert(tk.END, f_name)
            self.update_status(f"Found {len(files)} image files in {self.script_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not read directory: {e}")
            self.update_status(f"Error reading directory: {e}")

    def stage_rename(self):
        selected_target_idx = self.target_listbox.curselection()
        selected_current_idx = self.current_files_listbox.curselection()

        if not selected_target_idx:
            messagebox.showwarning("Selection Error", "Please select a target filename.")
            return
        if not selected_current_idx:
            messagebox.showwarning("Selection Error", "Please select a current image file to rename.")
            return

        target_name = self.target_listbox.get(selected_target_idx[0])
        current_name = self.current_files_listbox.get(selected_current_idx[0])

        # Check if current file is already staged
        if current_name in self.staged_renames:
            messagebox.showwarning("Staging Error", f"'{current_name}' is already staged to be renamed to '{self.staged_renames[current_name]}'.\nUnstage it first if you want to change its target.")
            return

        # Check if target name is already staged for another file
        if target_name in self.staged_renames.values():
            messagebox.showwarning("Staging Error", f"Target name '{target_name}' is already assigned to another file.\nChoose a different target name or unstage the existing assignment.")
            return
            
        # Check if target name would conflict with an existing file (that isn't the source file itself)
        target_path = os.path.join(self.script_dir, target_name)
        if os.path.exists(target_path) and current_name != target_name:
            messagebox.showwarning("Filename Conflict", f"The target filename '{target_name}' already exists in the directory.")
            return

        self.staged_renames[current_name] = target_name
        self.update_staged_listbox()
        self.update_status(f"Staged: '{current_name}' -> '{target_name}'")

    def unstage_rename(self):
        selected_staged_idx = self.staged_listbox.curselection()
        if not selected_staged_idx:
            messagebox.showwarning("Selection Error", "Please select a staged rename to remove.")
            return
        
        staged_entry_text = self.staged_listbox.get(selected_staged_idx[0])
        try:
            current_name = staged_entry_text.split(" -> ")[0].strip()
            if current_name in self.staged_renames:
                del self.staged_renames[current_name]
                self.update_staged_listbox()
                self.update_status(f"Unstaged rename for '{current_name}'")
            else:
                messagebox.showerror("Error", "Could not find the selected entry in staged renames data.")
        except IndexError:
            messagebox.showerror("Error", "Invalid format in staged renames list.")


    def update_staged_listbox(self):
        self.staged_listbox.delete(0, tk.END)
        for current_name, target_name in self.staged_renames.items():
            self.staged_listbox.insert(tk.END, f"{current_name} -> {target_name}")

    def process_renames_confirmation(self):
        if not self.staged_renames:
            messagebox.showinfo("No Renames", "No renames have been staged.")
            return

        summary = "The following renames will be performed:\n\n"
        for current, target in self.staged_renames.items():
            summary += f"'{current}'  ->  '{target}'\n"
        summary += "\nThis action cannot be undone easily. Are you sure you want to proceed?"

        if messagebox.askyesno("Confirm Renames", summary):
            self.execute_renames()

    def execute_renames(self):
        success_count = 0
        fail_count = 0
        skipped_count = 0
        details = []

        for current_name, target_name in list(self.staged_renames.items()): # Iterate copy
            current_path = os.path.join(self.script_dir, current_name)
            target_path = os.path.join(self.script_dir, target_name)

            if not os.path.exists(current_path):
                details.append(f"FAIL: Source file '{current_name}' not found (was it moved or deleted?).")
                fail_count += 1
                del self.staged_renames[current_name] # Remove from processed list
                continue

            if current_path == target_path:
                details.append(f"SKIP: Source and target '{current_name}' are the same.")
                skipped_count +=1
                del self.staged_renames[current_name]
                continue
                
            if os.path.exists(target_path):
                # This should ideally be caught during staging, but as a final check:
                details.append(f"FAIL: Target file '{target_name}' already exists. Skipping rename for '{current_name}'.")
                fail_count += 1
                # Do not remove from staged_renames here to allow user to fix and retry
                continue
            
            try:
                os.rename(current_path, target_path)
                details.append(f"SUCCESS: Renamed '{current_name}' to '{target_name}'")
                success_count += 1
                del self.staged_renames[current_name] # Remove successfully processed item
            except OSError as e:
                details.append(f"FAIL: Could not rename '{current_name}' to '{target_name}'. Error: {e}")
                fail_count += 1
                # Do not remove from staged_renames here
        
        self.update_staged_listbox() # Reflects remaining (failed) items
        self.populate_current_files() # Refresh file list

        result_message = f"Renaming Complete.\nSuccessful: {success_count}\nFailed: {fail_count}\nSkipped: {skipped_count}\n\nDetails:\n" + "\n".join(details)
        messagebox.showinfo("Rename Results", result_message)
        self.update_status(f"Processed. Success: {success_count}, Failed: {fail_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    root = tk.Tk()
    app = BatchRenamerApp(root)
    root.mainloop()