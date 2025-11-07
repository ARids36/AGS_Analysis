import pandas as pd
import numpy as np
from python_ags4 import AGS4
import tkinter as tk
from tkinter import filedialog, ttk
import os
from tabulate import tabulate

"""
ERES_CODE seem to link directly to the contaminant names based on their CAS number.
CAS numbers can be queried at https://webbook.nist.gov/chemistry/name-ser/
"""

# ---------- FUNCTIONS ----------
def load_file():
    """Loads an AGS file and reformats for display purposes"""
    global LAB_FILE, file_label, REFORMATTED_DF

    # --- Load file ---
    filepath = filedialog.askopenfilename(
        title="Select an AGS File",
        filetypes=(("AGS4 files", "*.ags"),("All files", "*.*")))

    if filepath:
        file_label.config(text=f"File Name: {os.path.basename(filepath)}")
        LAB_FILE = filepath
    else:
        file_label.config(text=f"File Name: No file selected")
        return

    # --- Load AGS data ---
    try:
        tables, headings = AGS4.AGS4_to_dataframe(LAB_FILE)
    except FileNotFoundError:
        print("AGS4 file not found")
        file_label.config(text=f"File Name: Invalid file")
        return

    # --- Extract lab data ---
    if 'ERES' in tables:
        lab_test_summary = tables['ERES']
        # Create a new DataFrame with selected columns and exclude the first two rows
        lab_results_df = lab_test_summary[['LOCA_ID', 'SAMP_ID', 'SPEC_DPTH', 'ERES_CODE', 'ERES_MATX', 'ERES_NAME',
                                           'ERES_RTXT']].iloc[2:]
        print('ERES table loaded')
    else:
        print("No ERES table")
        file_label.config(text=f"File Name: Invalid file")
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
    print('Data reformatted')


def analyse():
    """Compare data with the selected GAC"""
    global REFORMATTED_DF

    # --- Load GAC data ---
    with open(GAC[selected_gac.get()], "r") as data:
        gac_df = pd.read_csv(data, sep=",", encoding="utf-8-sig")
        print('GAC data loaded')

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
    print('Tables merged')

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

    print('Data analysed\n')

    if exceedances_df.empty:
        print('No exceedances identified')
    else:
        print('Data exceeding selected GAC:')
        print(exceedances_df)


def pass_func():
    """Bypass function for testing. Boop!"""
    print('boop')

# ---------- VARIABLES ----------
TITLE_FONT = ("Arial", 20, "bold")
BODY_FONT = ("Arial", 14,)
LAB_FILE = ""
GAC = {"Industrial Soil": "ind_soil_gac.csv",
       "Industrial Water": "ind_water_gac.csv",
       "Residential Soil": "res_soil_gac.csv",
       "Residential Water": "res_water_gac.csv"}
REFORMATTED_DF = []

# ---------- GUI ----------
# Initialise the main window object
root = tk.Tk()
root.title("Lab Analysis")
root.geometry("500x500")

# Add Labels
title = tk.Label(
    root,
    text="Lab Data Analysis",
    font=TITLE_FONT
)
title.grid(column=0, row=0, columnspan=2, padx=10, pady=10)

file_label = tk.Label(
    root,
    text="File Name: No file selected",
    font=BODY_FONT
)
file_label.grid(sticky="W", column=0, row=2, padx=5, pady=10, columnspan=2)

gac_label = tk.Label(
    root,
    text="Select GAC: ",
    font=BODY_FONT
)
gac_label.grid(sticky="W", column=0, row=3, padx=5, pady=10)

table_label = tk.Label(
    root,
    text="",
    font=BODY_FONT
)
table_label.grid(sticky="W", column=0, row=5, padx=5, pady=10, columnspan=3)

# Add buttons
upload_button = tk.Button(
    root,
    text="Select File",
    font=BODY_FONT,
    command=load_file
)
upload_button.grid(sticky="W", column=0, row=1, padx=5, pady=10)

disp_button = tk.Button(
    root,
    text="Display Data",
    font=BODY_FONT,
    command=lambda: table_label.config(text=tabulate(REFORMATTED_DF, headers='keys', tablefmt='psql')) # Messy - needs changing
)
disp_button.grid(sticky="W",column=1, row=1, padx=5, pady=10)

analyse_button = tk.Button(
    root,
    text="Analyse data",
    font=BODY_FONT,
    command=analyse
)
analyse_button.grid(sticky="W", column=0, row=4, padx=5, pady=10)

# Add dropdown
dropdown_options = ["Industrial Soil", "Industrial Water", "Residential Soil", "Residential Water"]
selected_gac = tk.StringVar(root)
selected_gac.set(dropdown_options[0])
dropdown_box = ttk.Combobox(root, textvariable=selected_gac, values=dropdown_options,
                            state="readonly", font=BODY_FONT)
dropdown_box.grid(sticky="W", column=1, row=3, padx=5, pady=10)
# For use in analysis button --- selected_gac.get() --- gets value from dropdown

# ---------- RUN ----------
if __name__ == "__main__":
    root.mainloop()