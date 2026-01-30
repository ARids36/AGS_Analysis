"""AGS File analysis:

This programme initialises a GUI to take laboratory AGS data and compare it against generic acceptance criteria,
returning the samples/ values that exceed the criteria.
Results are displayed as integrated tables that can be exported as .csv files

ERES_CODE in AGS link directly to the contaminant names based on their CAS number.
CAS numbers can be queried at https://webbook.nist.gov/chemistry/name-ser/

QUERIES:
Should <x values just represent the x value, or 0? Can use ERES_RVAL instead of ERES_RTXT to get number w/o < >

NOTES:
ERES_RVAL should be included in data scrape to reduce required < > removal logic
ERES_IQLF/ ERES_LQLF used to display whether < or > are present

TO DO:
Check all GAC data

SOLVED:
Fixed issue where sample depths were not extracted correctly
Add sample depths - previous code only picked first sample ID, removing any deeper samples
File name wrapped and window auto-sized
CSV export button added for filtered data
.xlsx save function to preserve formatting
Check box to display all data, not just exceedance
Dropdown to select varying SOM
Added User specific target capabilities
"""

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

        # Resize window if necessary
        root.update_idletasks()
        new_height = root.winfo_reqheight()
        current_width = root.winfo_width()
        root.geometry(f"{current_width}x{new_height}")

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
        lab_results_df = lab_test_summary[['LOCA_ID', 'SAMP_ID', 'SAMP_TOP', 'ERES_CODE', 'ERES_MATX', 'ERES_NAME',
                                           'ERES_RTXT']].iloc[2:]
        update_log('ERES table loaded')
    else:
        update_log("No ERES table")
        file_label.config(text=f"File Name: Invalid file")
        messagebox.showwarning("Invalid file", "No ERES table located in file - "
                                               "Please check data format")
        return

    # --- Reformat lab data ---
    REFORMATTED_DF = lab_results_df.pivot_table(
        index=['ERES_NAME', 'ERES_CODE'],
        columns=['LOCA_ID', 'SAMP_TOP'],
        values='ERES_RTXT',
        aggfunc='first'
    )

    # Create single string headers (eg, WS01 (0.3m))
    new_columns = []
    for col in REFORMATTED_DF.columns:
        loc = col[0]
        depth = col[1]
        # Handle formatting if depth is present/valid
        if pd.notna(depth) and str(depth).strip() != '':
            new_columns.append(f"{loc} ({depth}m)")
        else:
            new_columns.append(f"{loc}")

    REFORMATTED_DF.columns = new_columns

    # Get the unique ERES_NAME and ERES_CODE pairs from lab_results_df in their original order
    original_order = lab_results_df[['ERES_NAME', 'ERES_CODE']].drop_duplicates()

    # Reindex the reformatted_df to match the original order
    valid_keys = original_order.set_index(['ERES_NAME', 'ERES_CODE']).index.intersection(REFORMATTED_DF.index)
    REFORMATTED_DF = REFORMATTED_DF.reindex(valid_keys)

    # Reset the index to make ERES_NAME and ERES_CODE regular columns
    REFORMATTED_DF = REFORMATTED_DF.reset_index()

    # Define the data columns to check for data dynamically (excluding the name/code columns)
    data_columns = [col for col in REFORMATTED_DF.columns if col not in ['ERES_NAME', 'ERES_CODE']]

    # Filter out rows where all specified data columns are NaN
    REFORMATTED_DF = REFORMATTED_DF.dropna(subset=data_columns, how='all')
    update_log("Data reformatted")


def analyse(ref_data):
    """Compare data with the selected GAC

    Keyword arguments:
        ref_data (pandas.DataFrame) -- Dataframe containing formatted data
    """
    global FILTERED_AGS, FILTERED_DF, SELECTED_GAC, CURRENT_GAC_LIST, SELECTED_SOM

    try:
        # --- Load GAC data ---
        if SELECTED_GAC.get() == "Custom Criteria":
            filepath = filedialog.askopenfilename(
                title="Select a custom acceptance criteria",
                filetypes=(("CSV files", "*.csv"), ("All files", "*.*")))

            if filepath:
                filename = filepath
            else:
                update_log("Unable to load custom criteria")
                messagebox.showwarning("No Criteria Loaded", "Unable to load file - check file name and path")
                return
        else:
            filename = GAC[SELECTED_GAC.get()]+SOM[SELECTED_SOM.get()]+".csv"

        data_file_path = resource_path(os.path.join('data', filename))
        with open(data_file_path, "r") as data:
            gac_df = pd.read_csv(data, sep=",")

            if 'ï»¿ERES_NAME' in gac_df.columns:
                gac_df.rename(columns={'ï»¿ERES_NAME': 'ERES_NAME'}, inplace=True)

        FILTERED_AGS = filter_raw_data_by_gac(gac_df)
        if FILTERED_AGS:
            export_ags_button.config(state="normal")
            export_csv_button.config(state="normal")
            export_xlsx_button.config(state="normal")
        else:
            export_ags_button.config(state="disabled")
            export_csv_button.config(state="disabled")
            export_xlsx_button.config(state="disabled")

        # --- Merge dataframes ---
        names_list = ['ERES_NAME', 'ERES_CODE']
        gac_list = np.array(gac_df.columns.values[2:]).tolist()
        CURRENT_GAC_LIST = gac_list
        header_list = names_list + gac_list
        merged_df = pd.merge(ref_data, gac_df[header_list], on=['ERES_NAME', 'ERES_CODE'], how='left')

        # Restore original ERES order
        original_order_index = ref_data[['ERES_NAME', 'ERES_CODE']].drop_duplicates()
        merged_df = merged_df.set_index(['ERES_NAME', 'ERES_CODE']).reindex(
            original_order_index.set_index(['ERES_NAME', 'ERES_CODE']).index).reset_index()
        update_log('Tables merged')

        # --- Prepare for Analysis ---
        limit_columns = gac_list
        lab_columns = [col for col in merged_df.columns if col not in ['ERES_NAME', 'ERES_CODE'] + limit_columns]

        # Create numeric shadow for mask calculation
        calc_df = merged_df.copy()
        for col in limit_columns:
            calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce')

        exceedance_mask = pd.Series(False, index=merged_df.index)
        exceeding_lab_columns = []

        # --- Masking Logic ---
        for lab_col in lab_columns:
            temp_lab_series = merged_df[lab_col].astype(str)
            greater_than_mask = temp_lab_series.str.contains('>', na=False)
            temp_lab_series = temp_lab_series.replace(r'.*<.*', '0', regex=True).str.replace('>', '', regex=False)
            numeric_lab_series = pd.to_numeric(temp_lab_series, errors='coerce')

            col_exceedance_mask = pd.Series(False, index=merged_df.index)
            for limit_col in limit_columns:
                aligned_numeric_lab = numeric_lab_series
                aligned_limit = calc_df[limit_col]

                numeric_exceedance = ((aligned_numeric_lab > aligned_limit)
                                      & aligned_numeric_lab.notna() & aligned_limit.notna())
                col_exceedance_mask = col_exceedance_mask | numeric_exceedance | greater_than_mask

            if col_exceedance_mask.any():
                exceeding_lab_columns.append(lab_col)
            exceedance_mask = exceedance_mask | col_exceedance_mask

        # --- Apply Sorting (Apply to merged_df so both views benefit) ---
        gac_names = gac_df['ERES_NAME'].dropna().unique().tolist()
        lab_names = merged_df['ERES_NAME'].dropna().unique().tolist()

        # Combine them, keeping GAC names at the top and adding unique lab names after
        combined_categories = gac_names + [name for name in lab_names if name not in gac_names]
        merged_df['ERES_NAME'] = pd.Categorical(
            merged_df['ERES_NAME'].astype(str).str.strip(),
            categories=combined_categories,
            ordered=True
        )
        merged_df = merged_df.sort_values('ERES_NAME')
        # Re-apply sorting to the mask as well to keep indices aligned
        exceedance_mask = exceedance_mask.reindex(merged_df.index)

        # --- Branching Logic for Display ---
        if ALL_DATA.get():
            # Show all data, keeping Name, Code, Lab Samples, then GAC columns
            display_df = merged_df[['ERES_NAME', 'ERES_CODE'] + lab_columns + limit_columns].copy()
            display_title = "Full Data Set (Screened)"
            update_log('Displaying full dataset')
        else:
            display_df = merged_df[exceedance_mask].copy()
            display_df = display_df[['ERES_NAME', 'ERES_CODE'] + exceeding_lab_columns + limit_columns]
            display_title = "Threshold Exceedances"
            update_log('Displaying exceedances only')

        FILTERED_DF = display_df
        update_log('Data analysed')

        if display_df.empty:
            update_log('No data matches the current filter')
        else:
            table_name = f"Screened {file_label['text']} - {SELECTED_GAC.get()} {SELECTED_SOM.get()}"
            display_data(table_name, display_df, analysis=True, gac=gac_list)

    except Exception as e:
        update_log(f'Error during analysis: {str(e)}')
        messagebox.showerror("Analysis Error", f"An error occurred: {str(e)}")


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

    eres_metadata = full_eres_df.iloc[:2].copy()
    eres_data = full_eres_df.iloc[2:].copy()

    if 'ï»¿ERES_NAME' in gac_df.columns:
        gac_df.rename(columns={'ï»¿ERES_NAME': 'ERES_NAME'}, inplace=True)

    # Filter ONLY the data rows
    # Merge resets the index, so we restore it to match eres_data
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
            AGS4.dataframe_to_AGS4(tables=FILTERED_AGS, headings=AGS_HEADINGS, filepath=save_path)
            update_log(f"File saved: {os.path.basename(save_path)}")
            messagebox.showinfo("Success", "AGS file exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")


def export_csv_file():
    """Saves the filtered exceeding data to a new .csv file"""
    global FILTERED_DF

    if FILTERED_DF.empty:
        messagebox.showinfo("Export", "No analysed data to export. Please Run Analysis first.")
        return

    save_path = filedialog.asksaveasfilename(
        title="Save CSV File",
        defaultextension=".csv",
        filetypes=(("CSV files", "*.csv"), ("All files", "*.*"))
    )

    if save_path:
        try:
            FILTERED_DF.to_csv(save_path, index=False, header=True)
            update_log(f"File saved: {os.path.basename(save_path)}")
            messagebox.showinfo("Success", "CSV file exported successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")


def export_xlsx_file():
    """Saves the filtered exceeding data to a new .xlsx file with color coding"""
    global FILTERED_DF, CURRENT_GAC_LIST

    if FILTERED_DF.empty or not CURRENT_GAC_LIST:
        messagebox.showinfo("Export", "No analysed data to export. Please Run Analysis first.")
        return

    save_path = filedialog.asksaveasfilename(
        title="Save Excel File",
        defaultextension=".xlsx",
        filetypes=(("Excel files", "*.xlsx"), ("All files", "*.*"))
    )

    if save_path:
        try:
            # Identify columns based on the same logic as display_data()
            all_cols = FILTERED_DF.columns.tolist()
            names_list = ['ERES_NAME', 'ERES_CODE']
            lab_headers = [c for c in all_cols if c not in names_list + CURRENT_GAC_LIST]

            def highlight_exceedances(df):
                # Shadow dataframe for numeric comparison
                calc_df = df.copy()
                for col in lab_headers + CURRENT_GAC_LIST:
                    calc_df[col] = calc_df[col].astype(str).replace(r'.*<.*', '0', regex=True)
                    calc_df[col] = calc_df[col].replace(r'[^0-9.\-]', '', regex=True)
                    calc_df[col] = pd.to_numeric(calc_df[col], errors='coerce')

                standards = calc_df[CURRENT_GAC_LIST].min(axis=1).fillna(float('inf'))

                style_df = pd.DataFrame('', index=df.index, columns=df.columns)
                for col in lab_headers:
                    mask = calc_df[col] > standards
                    style_df.loc[mask, col] = 'background-color: #FFCCCB'

                return style_df

            # Apply styles and export
            styled_df = FILTERED_DF.style.apply(highlight_exceedances, axis=None)
            styled_df.to_excel(save_path, index=False, engine='openpyxl')

            update_log(f"Excel file saved: {os.path.basename(save_path)}")
            messagebox.showinfo("Success", "Excel file exported successfully with formatting.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save Excel file: {str(e)}")


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
        for col in data.select_dtypes(['category']).columns:
            data[col] = data[col].astype(str)
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


def handle_gac_box(event):
    choice = SELECTED_GAC.get()
    print(f"Selected GAC: {choice}")

    if choice == "Industrial Water" or choice == "Residential Water":
        som_box.config(state="disabled")
        SELECTED_SOM.set("")
    else:
        SELECTED_SOM.set(som_options[0])
        som_box.config(state="enabled")

    root.update_idletasks()
    new_height = root.winfo_reqheight()
    current_width = root.winfo_width()
    root.geometry(f"{current_width}x{new_height}")


def pass_func():
    """Bypass function for testing. Boop!"""
    print('boop')
    update_log('boop')

# ---------- VARIABLES ----------
LAB_FILE = ""
GAC = {"Industrial Soil": "ind_soil_gac",
       "Industrial Water": "ind_water_gac",
       "Residential Soil": "res_soil_gac",
       "Residential Soil (Plant Uptake)": "res_soil_gac_plant",
       "Residential Water": "res_water_gac"}
SOM = {"1%": "_1",
       "2.5%": "_2-5",
       "6%": "_6",
       "": ""}
REFORMATTED_DF = pd.DataFrame([])
RAW_DATA = {}       # To store the full dictionary of AGS groups (LOCA, SAMP, ERES, etc.)
AGS_HEADINGS = {}   # To store the headers/units/types for the AGS file
FILTERED_AGS = {}   # To store the results that exceed criteria for export
FILTERED_DF = pd.DataFrame([]) # To store results as a printable df
CURRENT_GAC_LIST = [] # To store GAC headers for Excel export

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
root.resizable(False, False) # Window sized after widgets added

# Add header/ footer
header = Canvas(root, width=360, height=30, bd=0, highlightthickness=0)
head_file_path = resource_path(os.path.join('data', 'header_pic.png'))
header_img = PhotoImage(file=head_file_path)
header.create_image(0, 0, image=header_img)

footer = Canvas(root, width=360, height=30, bd=0, highlightthickness=0)
foot_file_path = resource_path(os.path.join('data', 'footer_pic.png'))
footer_img = PhotoImage(file=foot_file_path)
footer.create_image(0, 0, image=footer_img)

# Add Labels
title = tk.Label(
    root,
    text="Ags Screening Software",
    font=TITLE_FONT,
    bg=ORANGE
)

file_label = tk.Label(
    root,
    text="No file selected",
    font=BUTTON_FONT,
    bg=ORANGE,
    wraplength=180
)

gac_label = tk.Label(
    root,
    text="Select GAC: ",
    font=BUTTON_FONT,
    bg=ORANGE
)

som_label = tk.Label(
    root,
    text="Select SOM%: ",
    font=BUTTON_FONT,
    bg=ORANGE
)

version_label = tk.Label(
    root,
    text=f"{__version__}",
    font=("Calibri", 8),
)

# Add buttons
upload_button = tk.Button(
    root,
    text="Select File",
    font=BUTTON_FONT,
    command=load_file
)

disp_button = tk.Button(
    root,
    text="Display Data",
    font=BUTTON_FONT,
    command=lambda:display_data(file_label['text'], REFORMATTED_DF)
)

analyse_button = tk.Button(
    root,
    text="Analyse data",
    font=BUTTON_FONT,
    command=lambda:analyse(REFORMATTED_DF)
)

help_button = tk.Button(
    root,
    text="Help",
    font=("Calibri", 8),
    command=lambda: os.startfile('README.md')
)

export_ags_button = tk.Button(
    root,
    text="Export .ags",
    font=BUTTON_FONT,
    command=export_ags_file,
    state="disabled" # Disabled until analysis is run
)

export_csv_button = tk.Button(
    root,
    text="Export .csv",
    font=BUTTON_FONT,
    command=export_csv_file,
    state="disabled" # Disabled until analysis is run
)

export_xlsx_button = tk.Button(
    root,
    text="Export .xlsx",
    font=BUTTON_FONT,
    command=export_xlsx_file,
    state="disabled" # Disabled until analysis is run
)

# Add dropdowns
gac_options = ["Industrial Water", "Residential Water", "Industrial Soil",
               "Residential Soil", "Residential Soil (Plant Uptake)", "Custom Criteria"]
SELECTED_GAC = tk.StringVar(root)
SELECTED_GAC.set(gac_options[0])
gac_box = ttk.Combobox(root, textvariable=SELECTED_GAC, values=gac_options,
                       state="readonly", font=TEXT_FONT)
gac_box.bind("<<ComboboxSelected>>", handle_gac_box)

som_options = ["1%", "2.5%", "6%"]
SELECTED_SOM = tk.StringVar(root)
SELECTED_SOM.set("")
som_box = ttk.Combobox(root, textvariable=SELECTED_SOM, values=som_options,
                       state="readonly", font=TEXT_FONT)
som_box.config(state="disabled")

# Add log box
log_container = tk.Frame(root, padx=5, pady=10 ,bg=ORANGE)
scrollbar = tk.Scrollbar(log_container)
log_widget = tk.Text(log_container,
                     wrap="word",  # Wrap lines at word boundaries
                     yscrollcommand=scrollbar.set,  # Link scrollbar to Text widget
                     height=10,  # Initial height in lines
                     width=40,
                     bg='white',
                     bd=1,  # Border width
                     relief="sunken")  # Sunken relief for a box look
scrollbar.config(command=log_widget.yview)
log_widget.config(state="disabled")

# Add checkbox
ALL_DATA = tk.BooleanVar()
display_check = tk.Checkbutton(
    root,
    text="Display all data?",
    variable=ALL_DATA,
    onvalue=True,
    offvalue=False,
    bg=ORANGE
)

# Widget placement
header.grid(row=0, column=0, columnspan=3)
footer.grid(row=9, column=0, columnspan=3)
title.grid(column=0, row=1, columnspan=3, padx=10, pady=10)
file_label.grid(sticky="W", column=1, row=2, padx=5, pady=10, columnspan=2)
gac_label.grid(sticky="W", column=0, row=3, padx=5, pady=10)
som_label.grid(sticky="W", column=0, row=4, padx=5)
version_label.grid(sticky="W", column=0, row=9, padx=5, pady=5)
upload_button.grid(sticky="W", column=0, row=2, padx=5, pady=10)
disp_button.grid(sticky="E",column=2, row=5, padx=5, pady=15)
analyse_button.grid(sticky="W", column=0, row=5, padx=5, pady=15)
help_button.grid(sticky="E", column=2, row=9, padx=5, pady=5)
export_ags_button.grid(sticky="W", column=0, row=7, padx=5, pady=10)
export_csv_button.grid(column=1, row=7, padx=5, pady=10)
export_xlsx_button.grid(sticky="E", column=2, row=7, padx=5, pady=10)
gac_box.grid(sticky="", column=1, row=3, padx=5, columnspan=2)
som_box.grid(sticky="", column=1, row=4, padx=5, columnspan=2)
log_container.grid(row=8, column=0, columnspan=3, sticky=tk.N+tk.E+tk.W+tk.S)
log_container.grid_columnconfigure(0, weight=1)
log_container.grid_rowconfigure(1, weight=1)
scrollbar.grid(row=1, column=1, sticky=tk.N+tk.S)
log_widget.grid(row=1, column=0, sticky=tk.N + tk.E + tk.W + tk.S)
display_check.grid(row=6, column=0, sticky=tk.N+tk.W, padx=5)

# Size window
root.update_idletasks()
new_height = root.winfo_reqheight()
current_width = root.winfo_width()
root.geometry(f"{current_width}x{new_height}")

# ---------- RUN ----------
if __name__ == "__main__":
    root.mainloop()
