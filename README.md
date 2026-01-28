# Ags Screening Software
### v1.2.0-beta

**! This is a prototype software, still in development. Please check all results for inaccuracies before using them for
reporting. This may arise from an error in the programmes logic, or errors in the included GAC data. Please report 
any errors to Adam R !**

If you have any feedback, improvements or requests for future functionality, please let me know.

## Intro 
Ags Screening Software is a simple app that allows the upload of lab data in the .ags format, for comparison against
the relevant GAC and user uploaded criteria. The screened data is displayed as a standalone table, highlighting 
all values above the GAC, and can be exported as an .ags, .csv and .xlsx file (including formatting) for inclusion
in reporting or further analysis through other apps.
### New in this version (1.2.0-beta)
- Sample depths added to sample names
- .csv export button added
- .xlsx export button added (preserves exceedance shading)
- Option to display all data in screening (not just exceedances)
- Varying SOM% for soil GAC
- Option to use user specified screening criteria
- UI improvements
### Planned features
- Additional statistical analysis of data (outliers, means, min/ max etc.)
- Let me know what you need!
## Quick start guide
- Press 'Select File' to open the explorer and select the desired .ags data
- The selected file name will now be displayed to the right of the button
- Use the dropdown menu to select the relevant GAC
- If using a soil GAC, selected the SOM% from the other dropdown - default is 1%
- Press 'Display Data' to display all the lab data in a standalone table
- Press 'Analyse Data' to compare data against the selected GAC
- This will generate a table displaying any samples that recorded GAC exceedances. Specific contaminants exceeded 
will be highlighted in red
- To display all non-exceedance data alongside, select the checkbox below and regenerate
- Use the export buttons to export the screened dataset to your desired format
- If no exceedances are recorded, no table will be displayed, and the user is prompted in the notice board
### Notes on functionality
- Any values recorded below the laboratory detection limit (eg, <2.0) shall be treated as the value 0, regardless of
the GAC for that contaminant
- To use a custom screening criteria, use the template included in the folder. Headers and the first 2 columns must
remain the same, and the desired concentration added in the 3rd column
