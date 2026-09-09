Name = "Database"

[FileDB]
Path							= ".\Saves"		// Path of the database (relative to the program directory)
BackupPath						= "Backup\"		// This is added to Path, before the dated directories below  (".\Saves\Backup\2002-11-27_1800")
AutoSaveFrequency				= 0				// (3) How many turns will pass before auto-saving
AutoSaveOnExit					= 1				// (1) Should an autosave be done on exit
AutoSaveDateTimeStampedRate		= 0				// (10) Every X times an autosave is done, create as "Auto Save YYYY-MM-DD-HHMM".  0=Do not use this feature.
												//      Default values would do this every hour.  (10 x 3 turns == every 60 minutes)

[SQL]
UseSQL							= 0				// (0) 0 = use flat file, 1 = use SQL
DSN								= "SFC3;"		// DSN of database to connect to (can be local, shared, over the internet, whatever!)
DumpLog							= 3				// 0 = log nothing, 1 = log each command in separate files, 2 = use one file, 3 = log into one file and separate files
TransferFromFlat				= 1				// (0) WARNING: Dangerous.  0 = ignore.  1 = Load from current flat memory database and transfer contents into SQL.  This is a one time only
												//     option.  It ONLY takes affect if UseSQL=1.  You MUST make sure the SQL database tables are reset and cleared first.