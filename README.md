# Ags Screening Software
v1.1.0-alpha

**! This is a prototype software, still in development. Please check all results for inaccuracies before using them for
reporting. This may arise from an error in the programmes logic, or errors in the included GAC data. Please report 
any errors to Adam R !**

If you have any feedback, improvements or requests for future functionality, please let me know.
## Intro 
Ags Screening Software is a simple app that allows the upload of lab data in the .ags format, for comparison against
the relevant GAC. The screened data is displayed as a standalone table, highlighting all values above the GAC,
and can be saved as a .csv file for inclusion in reporting or further analysis through other apps.
### Current Functionality
- Import .ags files directly from the explorer
- Display data as a pop-out table
- Compare the data against the relevant GAC for the site and display the exceedances in a table
- This table can be copied or saved as a .csv for use in other formats
### Planned features
- Export the screened data as an .ags file to be imported into QGIS and other relevant software
- Additional statistical analysis of data (outliers, means, min/ max etc.)
## Quick start guide
- Press 'Select File' to open the explorer and select the desired .ags data
- The selected file name will now be displayed to the right of the button
- Use the dropdown menu to select the relevant GAC
- Press 'Display Data' to display all the lab data in a standalone table
- Press 'Analyse Data' to compare data against the selected GAC
- This will generate a table displaying any samples that recorded GAC exceedances. Specific contaminants exceeded 
will be highlighted in red
- To save tables as csv, select 'Save' from the toolbar in the pop-out window. Under 'Save as type' select
'All files', and under 'File name' enter "yourFileName.csv", replacing with your own file name, but keeping .csv
- To save the filtered data as a .ags file, use the button "Export .AGS", which should no longer be greyed out
- If no exceedances are recorded, no table will be displayed, and the user is prompted in the notice board
### Notes on functionality
- Any values recorded below the laboratory detection limit (eg, <2.0) shall be treated as the value 0, regardless of
the GAC for that contaminant
- GAC data is made up of 4 data sets: Residential Soils, Commercial Soils, Residential Waters, Commercial Waters. 
These data are preloaded into the app, taken from the screening criteria spreadsheets. Alternative data sets can't
be uploaded at this stage 
