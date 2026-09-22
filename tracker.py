from ultralytics import YOLO
import numpy as np

class PersonTracker:
    def __init__(self, model_path="yolov8n.pt"):
        # Load YOLOv8 model
        self.model = YOLO(model_path)
        
    def track(self, frame):
        """
        Runs YOLOv8 + ByteTrack tracking on a BGR image.
        Returns a list of tracked bounding boxes with IDs:
        [{'track_id': int, 'bbox': [x1, y1, x2, y2], 'conf': float}]
        """
        # Run tracker with persist=True, targeting class 0 (person)
        # Using default 'bytetrack.yaml'
        results = self.model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],
            verbose=False
        )
        
        tracked_objects = []
        if len(results) > 0 and results[0].boxes is not None:
            boxes = results[0].boxes
            if boxes.id is not None:
                for box in boxes:
                    # Retrieve coordinates and track id
                    track_id = int(box.id[0].item())
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0].item())
                    
                    tracked_objects.append({
                        'track_id': track_id,
                        'bbox': [x1, y1, x2, y2],
                        'conf': conf
                    })
        return tracked_objects
