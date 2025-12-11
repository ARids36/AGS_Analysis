"""AGS File analysis:

This programme initialises a GUI to take laboratory AGS data and compare it against generic acceptance criteria,
returning the samples/ values that exceed the criteria.
Results are displayed as integrated tables that can be exported as .csv files

ERES_CODE in AGS link directly to the contaminant names based on their CAS number.
CAS numbers can be queried at https://webbook.nist.gov/chemistry/name-ser/
"""

from __version__ import __version__

# ---------- IMPORTS ----------
import pandas as pd
from pandastable import Table
import numpy as np
from python_ags4 import AGS4
import tkinter as tk
from tkinter import Canvas, PhotoImage, messagebox
from tkinter import filedialog, ttk
import os
import sys


# ---------- FUNCTIONS ----------
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Falls back to the current directory when running as a normal script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def load_file():
    """Loads an AGS file and reformats for display purposes"""
    global LAB_FILE, file_label, REFORMATTED_DF

    # --- Load file ---
    filepath = filedialog.askopenfilename(
        title="Select an AGS File",
        filetypes=(("AGS4 files", "*.ags"), ("All files", "*.*")))

    if filepath:
        file_label.config(text=f"{os.path.basename(filepath)}")
        LAB_FILE = filepath
    else:
        file_label.config(text=f"No file selected")
        update_log("Unable to load file")
        messagebox.showwarning("No File Loaded", "Unable to load file - check file name and path")
        return

    # --- Load AGS data ---
    try:
        tables, headings = AGS4.AGS4_to_dataframe(LAB_FILE)
    except FileNotFoundError:
        update_log("AGS4 file not found - check file type")
        file_label.config(text=f"Invalid file")
        messagebox.showwarning("Invalid file", "No AGS data located within file - "
                                               "please check file type and data format")
        return

    # --- Extract lab data ---
    if 'ERES' in tables:
        lab_test_summary = tables['ERES']
        # Create a new DataFrame with selected columns and exclude the first two rows
        lab_results_df = lab_test_summary[['LOCA_ID', 'SAMP_ID', 'SPEC_DPTH', 'ERES_CODE', 'ERES_MATX', 'ERES_NAME',
                                           'ERES_RTXT']].iloc[2:]
        update_log('ERES table loaded')
    else:
        update_log("No ERES table")
        file_label.config(text=f"File Name: Invalid file")
        messagebox.showwarning("Invalid file", "No ERES table located in file - "
                                               "Please check data format")
        return

    # --- Reformat lab data ---
    REFORMATTED_DF = lab_results_df.pivot_table(index=['ERES_NAME', 'ERES_CODE'], columns='LOCA_ID',
                                                values='ERES_RTXT',
                                                aggfunc='first')

    # Get the unique ERES_NAME and ERES_CODE pairs from lab_results_df in their original order
    original_order = lab_results_df[['ERES_NAME', 'ERES_CODE']].drop_duplicates()

    # Reindex the reformatted_df to match the original order
    REFORMATTED_DF = REFORMATTED_DF.reindex(original_order.set_index(['ERES_NAME', 'ERES_CODE']).index)

    # Reset the index to make ERES_NAME and ERES_CODE regular columns
    REFORMATTED_DF = REFORMATTED_DF.reset_index()

    # Define the LOCA_ID columns to check for data dynamically
    loca_id_columns = [col for col in REFORMATTED_DF.columns if col not in ['ERES_NAME', 'ERES_CODE']]

    # Filter out rows where all specified LOCA_ID columns are NaN
    REFORMATTED_DF = REFORMATTED_DF.dropna(subset=loca_id_columns, how='all')
    update_log("Data reformatted")


def analyse():
    """Compare data with the selected GAC"""
    global REFORMATTED_DF

    try:
        # --- Load GAC data ---
        data_file_path = resource_path(os.path.join('data', GAC[selected_gac.get()]))
        with open(data_file_path, "r") as data:
            gac_df = pd.read_csv(data, sep=",", encoding="utf-8-sig")

            # Rename the column causing error --- NOT VERY ROBUST - NEEDS ADDRESSING IN FUTURE - Encoding issue?
            if 'ï»¿ERES_NAME' in gac_df.columns:
                gac_df.rename(columns={'ï»¿ERES_NAME': 'ERES_NAME'}, inplace=True)

        # --- Merge dataframes ---
        names_list = ['ERES_NAME', 'ERES_CODE']
        gac_list = np.array(gac_df.columns.values[2:]).tolist()
        header_list = names_list + gac_list
        merged_df = pd.merge(REFORMATTED_DF,
                             gac_df[header_list],
                             on=['ERES_NAME', 'ERES_CODE'], how='left')

        # Get the original order of ERES_NAME and ERES_CODE from reformatted_df before merging
        original_order = REFORMATTED_DF[['ERES_NAME', 'ERES_CODE']].drop_duplicates()

        # Reindex the merged_df to match the original order
        merged_df = merged_df.set_index(['ERES_NAME', 'ERES_CODE']).reindex(
            original_order.set_index(['ERES_NAME', 'ERES_CODE']).index).reset_index()
        update_log('Tables merged')

        # --- Analyse exceedances ---
        exceedances_df = merged_df.copy()
        limit_columns = gac_list

        for col in limit_columns:
            exceedances_df[col] = pd.to_numeric(exceedances_df[col], errors='coerce')

        exceedances_df = exceedances_df.dropna(subset=limit_columns, how='all')

        lab_columns = [col for col in exceedances_df.columns if col not in ['ERES_NAME', 'ERES_CODE'] + limit_columns]

        exceedance_mask = pd.Series(False, index=exceedances_df.index)
        exceeding_lab_columns = []

        for lab_col in lab_columns:
            temp_lab_series = exceedances_df[lab_col].astype(str)
            greater_than_mask = temp_lab_series.str.contains('>', na=False)
            temp_lab_series = temp_lab_series.str.replace('<', '', regex=False).str.replace('>', '', regex=False)
            numeric_lab_series = pd.to_numeric(temp_lab_series, errors='coerce')

            col_exceedance_mask = pd.Series(False, index=exceedances_df.index)
            for limit_col in limit_columns:
                aligned_numeric_lab = numeric_lab_series.align(exceedances_df[limit_col])[0]
                aligned_limit = numeric_lab_series.align(exceedances_df[limit_col])[1]

                numeric_exceedance = ((aligned_numeric_lab > aligned_limit)
                                      & aligned_numeric_lab.notna() & aligned_limit.notna())

                col_exceedance_mask = col_exceedance_mask | numeric_exceedance | greater_than_mask.reindex(
                    col_exceedance_mask.index, fill_value=False)

            if col_exceedance_mask.any():
                exceeding_lab_columns.append(lab_col)

            exceedance_mask = exceedance_mask | col_exceedance_mask

        exceedances_df = exceedances_df[exceedance_mask].copy()

        final_columns = ['ERES_NAME', 'ERES_CODE'] + exceeding_lab_columns + limit_columns
        exceedances_df = exceedances_df[final_columns]

        update_log('Data analysed')

        if exceedances_df.empty:
            update_log('No exceedances identified')
        else:
            display_data("Threshold Exceedances", exceedances_df)

    except KeyError:
        update_log('Invalid file type')
        messagebox.showwarning("Invalid file", "Data not presented in AGS format - "
                                               "check AGS data is loaded as data file")


def display_data(table_name, data):
    """Display data in a pop-out GUI

    Keyword arguments:
    table_name -- Title of the table to be displayed
    data -- Data table to be displayed
    """
    if data.empty:
        update_log("No data to display")
        messagebox.showwarning("No data", "No data to display - please load a valid file")
    else:
        data_window = tk.Toplevel(root)
        data_window.title(table_name)
        # Add table widget - Create a Frame to hold the table.
        table_frame = tk.Frame(data_window)
        table_frame.pack(fill='both', expand=True)
        pt = Table(table_frame, dataframe=data, showtoolbar=True, showstatusbar=True)
        pt.show()
        pt.autoResizeColumns()


def update_log(message):
    """Update the log with the given update message"""
    if log_widget:
        log_widget.config(state="normal")
        # Add timestamp if necessary
        # timestamp = datetime.now().strftime("[%H:%M:%S]")
        # log_message = f"{timestamp} {message}\n"
        log_message = f"{message}\n"
        log_widget.insert(tk.END, log_message)
        log_widget.see(tk.END)
        log_widget.config(state="disabled")


def pass_func():
    """Bypass function for testing. Boop!"""
    print('boop')

# ---------- VARIABLES ----------
LAB_FILE = ""
GAC = {"Industrial Soil": "ind_soil_gac.csv",
       "Industrial Water": "ind_water_gac.csv",
       "Residential Soil": "res_soil_gac.csv",
       "Residential Water": "res_water_gac.csv"}
REFORMATTED_DF = pd.DataFrame([])

# Style
TITLE_FONT = ("Calibri", 20, "bold")
BUTTON_FONT = ("Calibri", 14)
TEXT_FONT = ("Calibri", 12)
ORANGE = "#F3933C"
WHITE= "#FFFFFF"

# ---------- GUI ----------
# Initialise the main window object
root = tk.Tk()
root.configure(background=ORANGE)
root.title("Lab Analysis")
root.geometry("360x395")
root.resizable(False, False)

# Add header/ footer
header = Canvas(root, width=360, height=26, bd=0, highlightthickness=0)
header_img = PhotoImage(file="data/header_pic.png")
header.create_image(0, 0, image=header_img)
header.grid(row=0, column=0, columnspan=2)

footer = Canvas(root, width=360, height=26, bd=0, highlightthickness=0)
footer_img = PhotoImage(file="data/footer_pic.png")
footer.create_image(0, 0, image=footer_img)
footer.grid(row=6, column=0, columnspan=2)

# Add Labels
title = tk.Label(
    root,
    text="Lab Data Analysis",
    font=TITLE_FONT,
    bg=ORANGE
)
title.grid(column=0, row=1, columnspan=2, padx=10, pady=10)

file_label = tk.Label(
    root,
    text="No file selected",
    font=BUTTON_FONT,
    bg=ORANGE
)
file_label.grid(sticky="W", column=1, row=2, padx=5, pady=10, columnspan=2)

gac_label = tk.Label(
    root,
    text="Select GAC: ",
    font=BUTTON_FONT,
    bg=ORANGE
)
gac_label.grid(sticky="W", column=0, row=3, padx=5, pady=10)

# Add buttons
upload_button = tk.Button(
    root,
    text="Select File",
    font=BUTTON_FONT,
    command=load_file
)
upload_button.grid(sticky="W", column=0, row=2, padx=5, pady=10)

disp_button = tk.Button(
    root,
    text="Display Data",
    font=BUTTON_FONT,
    command=lambda:display_data('Lab Data', REFORMATTED_DF)
)
disp_button.grid(sticky="E",column=1, row=4, padx=5, pady=15)

analyse_button = tk.Button(
    root,
    text="Analyse data",
    font=BUTTON_FONT,
    command=analyse
)
analyse_button.grid(sticky="W", column=0, row=4, padx=5, pady=15)

# Add dropdown
dropdown_options = ["Industrial Soil", "Industrial Water", "Residential Soil", "Residential Water"]
selected_gac = tk.StringVar(root)
selected_gac.set(dropdown_options[0])
dropdown_box = ttk.Combobox(root, textvariable=selected_gac, values=dropdown_options,
                            state="readonly", font=TEXT_FONT)
dropdown_box.grid(sticky="W", column=1, row=3, padx=5)
# For use in analysis button --- selected_gac.get() --- gets value from dropdown

# Add log box
log_container = tk.Frame(root, padx=5, pady=10 ,bg=ORANGE)
log_container.grid(row=5, column=0, columnspan=2, sticky=tk.N+tk.E+tk.W+tk.S)
log_container.grid_columnconfigure(0, weight=1)
log_container.grid_rowconfigure(1, weight=1)

# log_label = tk.Label(log_container, text="Log:", anchor='w', bg=ORANGE)
# log_label.grid(row=0, column=0, columnspan=2, sticky=tk.W + tk.E)

scrollbar = tk.Scrollbar(log_container)
scrollbar.grid(row=1, column=1, sticky=tk.N+tk.S)

log_widget = tk.Text(log_container,
                     wrap="word",  # Wrap lines at word boundaries
                     yscrollcommand=scrollbar.set,  # Link scrollbar to Text widget
                     height=5,  # Initial height in lines
                     width=40,
                     bg='white',
                     bd=1,  # Border width
                     relief="sunken")  # Sunken relief for a box look
log_widget.grid(row=1, column=0, sticky=tk.N + tk.E + tk.W + tk.S)
scrollbar.config(command=log_widget.yview)
log_widget.config(state="disabled")

# ---------- RUN ----------
if __name__ == "__main__":
    root.mainloop()