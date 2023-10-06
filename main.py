from __future__ import annotations
import sys, qrcode, cv2, time, os, requests, json, dotenv, logging
from datetime import date

dotenv.load_dotenv()

DEBUG = os.getenv("ENV") == "dev"
LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
logging.basicConfig(level=logging.DEBUG if DEBUG else LOG_LEVEL)
CACHE_ENABLED = os.getenv("CACHE_ENABLED") == "true"

class Main:

    _detector = cv2.QRCodeDetector()
    _camera = None

    _headers = {
        "Authorization": "Bearer " + os.getenv("NOTION_TOKEN"),
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    _meetings_dbid = os.getenv("NOTION_MEETINGS_DBID")
    _meetings_cache = None
    _meetings_cache_expiry = None
    
    _attendance_dbid = os.getenv("NOTION_ATTENDANCE_DBID")
    _attendance_cache = None
    _attendance_cache_expiry = None

    _users_cache = None
    _users_cache_expiry = None

    @property
    def camera():
        return Main._camera
    
    @camera.setter
    def camera(value: cv2.VideoCapture):
        if value is None or not value.isOpened():
            raise ValueError("Cannot open camera")
        Main._camera = value

    @camera.deleter
    def camera():
        if Main._camera is not None:
            Main._camera.release()


    def _read_notion_db(dbid: str):
        readUrl = f"https://api.notion.com/v1/databases/{dbid}/query"
        res = requests.request("POST", readUrl, headers=Main._headers)
        data = res.json()
        if res.status_code != 200:
            logging.error(f"Error reading users: {res.status_code}")
            logging.error(res.text)
            return
        if data["results"] is None or len(data["results"]) == 0:
            logging.error(f"Error reading users: no users found")
            return
        print(res.status_code)
        print(data["results"])

        with open('./full-properties.json', 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False)
        return data["results"]

    def read_attendance_db(force_refresh=False):
        if not (CACHE_ENABLED and not force_refresh and Main._attendance_cache_expiry and Main._attendance_cache_expiry > time.time()):
            Main._attendance_cache_expiry = time.time() + 600 # 10 minutes
            Main._attendance_cache = Main._read_notion_db(Main._attendance_dbid)
        return Main._attendance_cache
    
    def read_meetings_db(force_refresh=False):
        if not (CACHE_ENABLED and not force_refresh and Main._meetings_cache_expiry and Main._meetings_cache_expiry > time.time()):
            Main._meetings_cache_expiry = time.time() + 3600 # 1 hour
            Main._meetings_cache = Main._read_notion_db(Main._meetings_dbid)
        return Main._meetings_cache
    
    def read_users(force_refresh=False):
        if CACHE_ENABLED and not force_refresh and Main._users_cache_expiry and Main._users_cache_expiry > time.time():
            return Main._users_cache
        readUrl = f"https://api.notion.com/v1/users"
        res = requests.request("GET", readUrl, headers=Main._headers)
        data = res.json()
        if res.status_code != 200:
            logging.error(f"Error reading users: {res.status_code}")
            logging.error(res.text)
            return
        if data["results"] is None or len(data["results"]) == 0:
            logging.error(f"Error reading users: no users found")
            return

        with open('./full-properties.json', 'w', encoding='utf8') as f:
            json.dump(data, f, ensure_ascii=False)
        Main._users_cache = data["results"]
        Main._users_cache_expiry = time.time() + 3600 # 1 hour
        return data["results"]

    def read_page(page_id: str):
        readUrl = f"https://api.notion.com/v1/pages/{page_id}"
        res = requests.request("GET", readUrl, headers=Main._headers)
        if res.status_code != 200:
            logging.error(f"Error reading page: {res.status_code}")
            logging.error(res.text)
            return None
        data = res.json()
        logging.debug(f"Read page {page_id} with status {res.status_code}: {data}")
        return data

    def create_attendance(user, meeting) -> bool:

        title = user["name"].split(' ')[0] + date.today().strftime(" %m/%d")
        properties = {
            "Title": {
                "id": "title",
                "title": [
                    {
                        "text": {
                            "content": title,
                        },
                    }
                ]
            },
            "Meetings": {
                "id": "C%3A%5DG",
                "relation": [
                    {
                        "id": meeting["id"]
                    }
                ],
            },
            "Person": {
                "id": "f%7CFE",
                "people": [user]
            },
        }
        res = requests.request("POST", "https://api.notion.com/v1/pages", headers=Main._headers, data=json.dumps({
            "parent": {
                "type": "database_id",
                "database_id": Main._attendance_dbid
            },
            "properties": properties
        }))
        if res.status_code != 200:
            logging.error(f"Error creating attendance: {res.status_code}")
            logging.error(res.text)
            return False
        data = res.json()
        if Main._attendance_cache is not None:
            Main._attendance_cache.append(data)
        else:
            Main._attendance_cache = [data]
        Main.read_meetings_db(force_refresh=True)
        return True


    def read_qr_code(filename):
        """Read an image and read the QR code.
        
        Args:
            filename (string): Path to file
        
        Returns:
            qr (string): Value from QR code
        """
        
        try:
            img = cv2.imread(filename)
            value, points, straight_qrcode = Main._detector.detectAndDecode(img)
            if points is not None:
                print(f"Found QR code with value {value}")
            return value
        except:
            print("Error reading QR code")
            return


    def write_qr_code(value: str):
        print(f"Generating QR Code for {value} at qr.png")
        img = qrcode.make(value)
        img.save("qr.png")

    def loop():
        ret, frame = Main.camera.read()

        if not ret:
            logging.warning("Error reading frame from camera")
            return
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if DEBUG:
            cv2.imshow('Camera Feed', gray)
            cv2.waitKey(1)
        
        try:
            value, points, straight_qrcode = Main._detector.detectAndDecode(gray)
            if points is None:
                return
        except Exception as e:
            logging.warn(f"Error getting QR Code: {e}")
            return
        users = Main.read_users()
        target_user = None
        for user in users:
            if user['id'] == value:
                target_user = user
                break
        if target_user is not None:
            logging.debug(f"Found Notion user {target_user['name']} with id {target_user['id']}")
            today = date.today().strftime("%Y-%m-%d")
            print(f"today is {today}")
            meetings: list[dict] = Main.read_meetings_db()
            target_meeting = None
            for meeting in meetings:
                if meeting["properties"]["Date"]["date"] is None:
                    continue
                if meeting["properties"]["Date"]["date"]["start"] == today:
                    logging.debug(f"Found meeting {meeting['properties']['Name']['title'][0]['text']['content']} on {meeting['properties']['Date']['date']['start']}")
                    target_meeting = meeting
                    break
            if target_meeting is not None:
                for attendance in target_meeting["properties"]["Attendance"]["relation"]:
                    page = Main.read_page(attendance["id"])
                    if page is None or len(page["properties"]["Person"]["people"]) == 0:
                        logging.warn(f"Found attendance with id {page['id']} with no person associated with meeting on {today}")
                        return
                    print("PEOPLE")
                    print(page["properties"]["Person"]["people"])
                    person = page["properties"]["Person"]["people"][0]
                    person_id = person["id"]
                    if person_id == target_user["id"]:
                        logging.debug(f"User {target_user['name']} already checked in")
                        return
                    else:
                        print(f"User {target_user['name']} ({target_user['id']}) does not match user {person['name']} ({person_id})")
                logging.debug(f"Creating new attendance for user {target_user['name']} for meeting {target_meeting['properties']['Name']['title'][0]['text']['content']}")
                Main.create_attendance(target_user, target_meeting)
        else:
            logging.debug(f"Found invalid QR code value [{value}]")
        

    def main():
        if len(sys.argv) > 1:
            if sys.argv[1] == "read":
                Main.read_qr_code(sys.argv[2])
                return
            elif sys.argv[1] == "write":
                Main.write_qr_code(str(sys.argv[2]))
            elif sys.argv[1] == "loop":
                Main.camera = cv2.VideoCapture(0)
                while True:
                    Main.loop()
                    time.sleep(.25) # wait 250ms
            return
        else:
            print(f"Incorrect number of arguments. First argument should be read or write, second argument should be name of file to read or data for QR code")


if __name__ == "__main__":
    print(f"Starting Notion Attendance Taker {sys.argv[0]}")
    Main.main()
