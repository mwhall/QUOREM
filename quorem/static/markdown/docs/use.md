Title: Using QUOREM
This is the general user guide for those who want to access or input data using a QUOREM instance.

[TOC]

## Quick Start

The easiest way to get started is to input QIIME2 artifact (.qza) or visualization (.qzv) files.

In order to input artifact files, you must first create a **Process** and **Analysis**. Artifact files are deposited to a specific **Analysis**, and an **Analysis** is an instantiation of a given **Process**.

[Create a **Process** here](/process/create/) and then [create an **Analysis** here](/analysis/create/).

Next, go to the [Artifact upload page](/upload/artifact/) and insert a QIIME2 .qza/.qzv file. It will begin ingestion into the database, and you will receive a notification when it is complete. QUOREM will automatically identify and register any new **Samples** and **Features** (e.g., taxa, ASVs, OTUs) and they will begin to show up on their respective pages and through the search utilities.

## Next Steps

After you have ingested an artifact file or two in the database, you will notice that there are now **Samples** and **Results** available to browse, and possibly some **Features**. Next you may want to:

- Create an **Investigation** and edit it to contain the **Samples** from a given **Analysis**.
- Edit the **Process** you created and add **Steps** to it
- Search through your data with the [Search page](/search/)
- Download data in .csv/.xls form from the detail pages
