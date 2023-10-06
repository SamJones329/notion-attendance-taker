# Notion Attendance Taker
This is a program to test proof of concept for implementing a QR code-based daily meeting attendance system with a notion integration.

## Requirements
Run `pip install -r requirements.txt` to create an environment from the requirements file, but the notable dependencies are as follows. If you use opencv for other things, I would recommend just using the base environment, as otherwise you waste a lot of storage space.
- opencv-python - Video input & QR code detection/decoding
- qrcode - Generation of QR codes
- dotenv - Read environment variables

## Setup
First, set up an integration in your desired workspace. Ensure this integration has read and write access, as well as seeing user information (email not necessary).

Second, create the meetings and attendance databases. The meetings database should have a "Date" column set for the date of the meeting, as well as a "Attendance" relation column pointing to the attendance database. The attendance database should a "Person" column, and a relation column "Meeting" pointing to the meeting database.

Third, ensure the integration has access to the databases.

Fourth, set up a `.env` file in the project root directory containing the following environment variables.
- `NOTION_TOKEN` - The secret provided by the notion integration
- `NOTION_ATTENDANCE_DBID` - The id of the attendance database
- `NOTION_MEETINGS_DBID` - The id of the meetings database
- `ENV` - If set to "dev", forces logging to debug level
- `CACHE_ENABLED` - Determines whether or not to use caching for database pages, generally set to true

## Running
To run the program, you must pass in at least one command line argument.
- Loop - Runs the program as normal
- Read - Reads the value of a qr code at the file location specified by the next command line argument
- Write - writes the value specified in the next command line argument into a qr code, saved as "qr.png"; use this to write Notion user IDs into QR codes to scan by the program, automatically taking their attendance