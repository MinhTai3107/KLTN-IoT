from flask import Flask, Response, jsonify, request
from flask_cors import CORS
import cv2
import torch
import base64
import threading
import function.helper as helper
import function.utils_rotate as utils_rotate

app = Flask(__name__)
CORS(app)

# Load YOLO models
yolo_LP_detect = torch.hub.load('yolov5', 'custom', path='model/LP_detector_nano_61.pt', force_reload=True, source='local')
yolo_license_plate = torch.hub.load('yolov5', 'custom', path='model/LP_ocr_nano_62.pt', force_reload=True, source='local')
yolo_license_plate.conf = 0.60

# Open the webcam
vid = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = vid.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def capture_image():
    success, frame = vid.read()
    if success:
        plates = yolo_LP_detect(frame, size=640).pandas().xyxy[0].values.tolist()
        if plates:
            for plate in plates:
                x, y, w, h = int(plate[0]), int(plate[1]), int(plate[2] - plate[0]), int(plate[3] - plate[1])
                crop_img = frame[y:y+h, x:x+w]
                lp_text = helper.read_plate(yolo_license_plate, crop_img)
                if lp_text != "unknown":
                    _, buffer = cv2.imencode('.png', crop_img)
                    encoded_image = base64.b64encode(buffer).decode('utf-8')
                    return jsonify({
                        "licensePlate": lp_text,
                        "image": encoded_image
                    })
    return jsonify({"message": "No license plate detected"})

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    capture_thread = threading.Thread(target=capture_image)
    capture_thread.start()
    capture_thread.join()  # Ensure capture process completes before responding
    return capture_image()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)
