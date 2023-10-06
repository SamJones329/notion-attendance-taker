import cv2

if __name__ == "__main__":
    print(f"Testing Camera Feed")
    cam = cv2.VideoCapture(0)
    while True:
        cv2.imshow("Camera Feed", cam.read()[1])
        cv2.waitKey(1)