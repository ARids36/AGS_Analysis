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
import subprocess
from __version__ import __version__


# ---------- FUNCTIONS ----------
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller

    Keyword arguments:
        relative_path (string) -- the local file path
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Falls back to the current directory when running as a normal script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def load_file():
    """Loads an AGS file and reformats for display purposes"""
    global LAB_FILE, file_label, REFORMATTED_DF, RAW_DATA, AGS_HEADINGS

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
        RAW_DATA, AGS_HEADINGS = AGS4.AGS4_to_dataframe(LAB_FILE)
        tables = RAW_DATA  # Local variable for existing logic compatibility
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


def analyse(ref_data):
    """Compare data with the selected GAC

    Keyword arguments:
        ref_data (pandas.DataFrame) -- Dataframe containing formatted data
    """
    global FILTERED_AGS

    try:
        # --- Load GAC data ---
        data_file_path = resource_path(os.path.join('data', GAC[selected_gac.get()]))
        with open(data_file_path, "r") as data:
            gac_df = pd.read_csv(data, sep=",") #, encoding="utf-8-sig")

            # Rename the column causing error --- NOT VERY ROBUST - NEEDS ADDRESSING IN FUTURE - Encoding issue?
            if 'ï»¿ERES_NAME' in gac_df.columns:
                gac_df.rename(columns={'ï»¿ERES_NAME': 'ERES_NAME'}, inplace=True)

        FILTERED_AGS = filter_raw_data_by_gac(gac_df)
        if FILTERED_AGS:
            export_button.config(state="normal")  # Enable the export button
        else:
            export_button.config(state="disabled")

        # --- Merge dataframes ---
        names_list = ['ERES_NAME', 'ERES_CODE']
        gac_list = np.array(gac_df.columns.values[2:]).tolist()
        header_list = names_list + gac_list
        merged_df = pd.merge(ref_data,
                             gac_df[header_list],
                             on=['ERES_NAME', 'ERES_CODE'], how='left')

        # Get the original order of ERES_NAME and ERES_CODE from reformatted_df before merging
        original_order = ref_data[['ERES_NAME', 'ERES_CODE']].drop_duplicates()

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
            # temp_lab_series = temp_lab_series.str.replace('<', '', regex=False).str.replace('>', '', regex=False)
            temp_lab_series = temp_lab_series.replace(r'.*<.*', '0', regex=True).str.replace('>', '', regex=False) # Replaces <x values with 0
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

        # Strip whitespace from both dataframes to ensure matches
        gac_df['ERES_NAME'] = gac_df['ERES_NAME'].astype(str).str.strip()
        exceedances_df['ERES_NAME'] = exceedances_df['ERES_NAME'].astype(str).str.strip()

        # Create a categorical type for ERES_NAME based on the order in the GAC file
        # gac_df['ERES_NAME'] contains the names in the desired order
        desired_order = gac_df['ERES_NAME'].dropna().unique()

        # Convert ERES_NAME column to categorical with this specific order
        # Values in exceedances_df not in desired_order will become NaN (which is fine)
        exceedances_df['ERES_NAME'] = pd.Categorical(
            exceedances_df['ERES_NAME'],
            categories=desired_order,
            ordered=True
        )

        # Sort by the new categorical column
        exceedances_df = exceedances_df.sort_values('ERES_NAME')

        update_log('Data analysed')

        if exceedances_df.empty:
            update_log('No exceedances identified')
        else:
            display_data("Threshold Exceedances", exceedances_df, analysis=True, gac=gac_list)

    except KeyError:
        update_log('Invalid file type')
        messagebox.showwarning("Invalid file", "Data not presented in AGS format - "
                                               "check AGS data is loaded as data file")


def filter_raw_data_by_gac(gac_df):
    """
    Filters the RAW_DATA['ERES'] table to keep only rows that exceed the GAC.
    Preserves the first two rows (UNIT and TYPE) for valid AGS export.

    Keyword arguments:
        gac_df (pandas.DataFrame) -- Dataframe containing GAC data
    """
    if 'ERES' not in RAW_DATA:
        return None

    full_eres_df = RAW_DATA['ERES'].copy()

    # Separate Metadata (Rows 0-1) from Data (Rows 2+)
    eres_metadata = full_eres_df.iloc[:2].copy()
    eres_data = full_eres_df.iloc[2:].copy()

    # Clean GAC headers
    if 'ï»¿ERES_NAME' in gac_df.columns:
        gac_df.rename(columns={'ï»¿ERES_NAME': 'ERES_NAME'}, inplace=True)

    # Filter ONLY the data rows
    # Merge resets the index, so we must restore it to match eres_data
    merged = pd.merge(eres_data, gac_df, on=['ERES_NAME', 'ERES_CODE'], how='left')

    # Restore the original index to the merged dataframe
    merged.index = eres_data.index

    gac_limit_cols = [c for c in gac_df.columns if c not in ['ERES_NAME', 'ERES_CODE']]

    # Create mask using the restored index
    exceedance_mask = pd.Series(False, index=merged.index)

    clean_results = merged['ERES_RTXT'].astype(str).replace(r'.*<.*', '0', regex=True).str.replace('>', '', regex=False)
    numeric_results = pd.to_numeric(clean_results, errors='coerce')

    for limit_col in gac_limit_cols:
        limit_values = pd.to_numeric(merged[limit_col], errors='coerce')
        is_greater_symbol = merged['ERES_RTXT'].astype(str).str.contains('>')
        col_mask = (numeric_results > limit_values) | is_greater_symbol
        exceedance_mask = exceedance_mask | col_mask

    # Now the indices match, so this line will work
    filtered_data_rows = eres_data[exceedance_mask].copy()

    if filtered_data_rows.empty:
        return None

    # Recombine Metadata and Filtered Data
    final_eres = pd.concat([eres_metadata, filtered_data_rows], ignore_index=False)

    export_tables = RAW_DATA.copy()
    export_tables['ERES'] = final_eres

    return export_tables


def export_ags_file():
    """Saves the filtered exceeding data to a new .ags file"""
    global AGS_HEADINGS, FILTERED_AGS

    if not FILTERED_AGS:
        messagebox.showinfo("Export", "No analysed data to export. Please Run Analysis first.")
        return

    save_path = filedialog.asksaveasfilename(
        title="Save AGS File",
        defaultextension=".ags",
        filetypes=(("AGS4 files", "*.ags"), ("All files", "*.*"))
    )

    if save_path:
        try:
            # Use the library's built-in writer
            AGS4.dataframe_to_AGS4(tables=FILTERED_AGS, headings=AGS_HEADINGS, filepath=save_path)
            update_log(f"File saved: {os.path.basename(save_path)}")
            messagebox.showinfo("Success", "AGS file exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")


def display_data(table_name, data, analysis=False, gac=None):
    """Display data in a pop-out GUI

    Keyword arguments:
        table_name (string) -- Title of the table to be displayed
        data (pandas.DataFrame) -- Data table to be displayed
        analysis (bool) -- If True, values will be formatted relative to included GAC data
        gac (list) -- GAC head data
    """
    if data.empty:
        update_log("No data to display")
        messagebox.showwarning("No data", "No data to display - please load a valid file")
    else:
        # Remove NaN values and format headers - solve pandastable float issues
        data = data.fillna('')
        data.columns = [str(col) for col in data.columns]

        # Create table
        data_window = tk.Toplevel(root)
        data_window.title(table_name)
        # Add table widget - Create a Frame to hold the table.
        table_frame = tk.Frame(data_window)
        table_frame.pack(fill='both', expand=True)
        pt = Table(table_frame, dataframe=data, showtoolbar=True, showstatusbar=True)

        if analysis:
            gac_head = gac
            data_head = [x for x in list(data.columns.values)[2:] if x not in gac_head]

            # 'Shadow' data frame to convert everything to numeric values
            cols_to_clean = data_head + gac_head
            calc_df = data[cols_to_clean].copy()

            calc_df = calc_df.replace(r'.*<.*', '0', regex=True) # Remove if "<x" values should be treated as "x" and not "0"
            calc_df = calc_df.replace(r'[^0-9.\-]', '', regex=True)
            calc_df = calc_df.apply(pd.to_numeric, errors='coerce')
            # Ensures empty GAC fields can't be exceeded
            calc_standards = calc_df[gac_head].min(axis=1).fillna(np.inf)

            for col in data_head:
                mask = calc_df[col] > calc_standards
                # Apply shading to original dataset
                pt.setColorByMask(col, mask, '#FFCCCB')
            pt.redraw()

            # Exceedance data
            exceedance_mask = calc_df[data_head].gt(calc_standards, axis=0)
            total_exceedances = exceedance_mask.sum().sum()
            sample_counts = exceedance_mask.sum()
            exceedances_msg = (f"\nTotal Exceedances: {total_exceedances}\n"
                               f"{sample_counts}")
            update_log(exceedances_msg)

        pt.show()
        pt.autoResizeColumns() # Likely to depreciate in package soon


def update_log(message):
    """Update the log with the given update message

    Keyword arguments:
        message (string) -- Update message
    """
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
    update_log('boop')

# ---------- VARIABLES ----------
LAB_FILE = ""
GAC = {"Industrial Soil": "ind_soil_gac.csv",
       "Industrial Water": "ind_water_gac.csv",
       "Residential Soil": "res_soil_gac.csv",
       "Residential Water": "res_water_gac.csv"}
REFORMATTED_DF = pd.DataFrame([])
RAW_DATA = {}       # To store the full dictionary of AGS groups (LOCA, SAMP, ERES, etc.)
AGS_HEADINGS = {}   # To store the headers/units/types for the AGS file
FILTERED_AGS = {}   # To store the results that exceed criteria for export

# Style
TITLE_FONT = ("Calibri", 20, "bold")
BUTTON_FONT = ("Calibri", 14)
TEXT_FONT = ("Calibri", 12)
ORANGE = "#F3933C" # Geo2 orange
WHITE= "#FFFFFF"

# ---------- GUI ----------
# Initialise the main window object
root = tk.Tk()
root.configure(background=ORANGE)
root.title("Lab Analysis")
root.geometry("360x518")
root.resizable(False, False)

# Add header/ footer
header = Canvas(root, width=360, height=26, bd=0, highlightthickness=0)
head_file_path = resource_path(os.path.join('data', 'header_pic.png'))
header_img = PhotoImage(file=head_file_path)
header.create_image(0, 0, image=header_img)
header.grid(row=0, column=0, columnspan=2)

footer = Canvas(root, width=360, height=26, bd=0, highlightthickness=0)
foot_file_path = resource_path(os.path.join('data', 'footer_pic.png'))
footer_img = PhotoImage(file=foot_file_path)
footer.create_image(0, 0, image=footer_img)
footer.grid(row=7, column=0, columnspan=2)

# Add Labels
title = tk.Label(
    root,
    text="Ags Screening Software",
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

version_label = tk.Label(
    root,
    text=f"{__version__}",
    font=("Calibri", 8),
)
version_label.grid(sticky="W", column=0, row=7, padx=5, pady=5)

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
    command=lambda:analyse(REFORMATTED_DF)
)
analyse_button.grid(sticky="W", column=0, row=4, padx=5, pady=15)

help_button = tk.Button(
    root,
    text="Help",
    font=("Calibri", 8),
    command=lambda: os.startfile('README.md')
)
help_button.grid(sticky="E", column=1, row=7, padx=5, pady=5)

export_button = tk.Button(
    root,
    text="Export .AGS",
    font=BUTTON_FONT,
    command=export_ags_file,
    state="disabled" # Disabled until analysis is run
)
export_button.grid(sticky="W", column=0, row=5, padx=5)

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
log_container.grid(row=6, column=0, columnspan=2, sticky=tk.N+tk.E+tk.W+tk.S)
log_container.grid_columnconfigure(0, weight=1)
log_container.grid_rowconfigure(1, weight=1)

scrollbar = tk.Scrollbar(log_container)
scrollbar.grid(row=1, column=1, sticky=tk.N+tk.S)

log_widget = tk.Text(log_container,
                     wrap="word",  # Wrap lines at word boundaries
                     yscrollcommand=scrollbar.set,  # Link scrollbar to Text widget
                     height=10,  # Initial height in lines
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
