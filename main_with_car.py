import cv2
import numpy as np
import time
import os
import torch
import torch.nn.functional as F
from collections import defaultdict, deque
from ultralytics import YOLO
import logging

# Import the smart car controller
from car_controller import SmartCarController

# Configure logging
logging.basicConfig(level=logging.INFO)  # Change to DEBUG for more detailed output
logger = logging.getLogger(__name__)

class FairMOTTracker:
    """Simple FairMOT-style tracker implementation"""
    def __init__(self, model_path):
        self.model_path = model_path
        self.tracks = {}
        self.next_id = 1
        self.max_age = 30
        self.min_hits = 3
        self.iou_threshold = 0.3
        self.feature_threshold = 0.7
        
        # Load pretrained model if available
        if os.path.exists(model_path):
            try:
                self.pretrained_weights = torch.load(model_path, map_location='cpu')
                logger.info(f"Loaded FairMOT pretrained weights from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load pretrained weights: {e}")
                self.pretrained_weights = None
        else:
            logger.warning(f"Pretrained model not found at {model_path}")
            self.pretrained_weights = None
    
    def extract_features(self, frame, bbox):
        """Extract features from detection bbox"""
        x1, y1, x2, y2 = bbox
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(frame.shape[1], x2), min(frame.shape[0], y2)
        
        if x2 <= x1 or y2 <= y1:
            return np.random.rand(128)  # Return random feature if invalid bbox
        
        # Extract ROI and resize to standard size
        roi = frame[y1:y2, x1:x2]
        roi = cv2.resize(roi, (64, 128))
        
        # Simple feature extraction (color histogram + HOG-like features)
        # In real FairMOT, this would be done by CNN backbone
        hist_b = cv2.calcHist([roi], [0], None, [32], [0, 256])
        hist_g = cv2.calcHist([roi], [1], None, [32], [0, 256])
        hist_r = cv2.calcHist([roi], [2], None, [32], [0, 256])
        
        # Combine histograms and normalize
        features = np.concatenate([hist_b.flatten(), hist_g.flatten(), hist_r.flatten()])
        features = features / (np.linalg.norm(features) + 1e-6)
        
        # Pad to 128 dimensions
        if len(features) < 128:
            features = np.pad(features, (0, 128 - len(features)), mode='constant')
        else:
            features = features[:128]
        
        return features
    
    def calculate_iou(self, bbox1, bbox2):
        """Calculate IoU between two bounding boxes"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i <= x1_i or y2_i <= y1_i:
            return 0.0
        
        intersection = (x2_i - x1_i) * (y2_i - y1_i)
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def calculate_feature_similarity(self, feat1, feat2):
        """Calculate cosine similarity between features"""
        dot_product = np.dot(feat1, feat2)
        norm_product = np.linalg.norm(feat1) * np.linalg.norm(feat2)
        return dot_product / (norm_product + 1e-6)
    
    def update(self, frame, detections):
        """Update tracker with new detections"""
        if not detections:
            # Age existing tracks
            for track_id in list(self.tracks.keys()):
                self.tracks[track_id]['age'] += 1
                if self.tracks[track_id]['age'] > self.max_age:
                    del self.tracks[track_id]
            return []
        
        # Extract features for all detections
        for detection in detections:
            detection['features'] = self.extract_features(frame, detection['bbox'])
        
        # Match detections to existing tracks
        matched_tracks = []
        unmatched_detections = list(range(len(detections)))
        
        for track_id, track in self.tracks.items():
            best_match_idx = -1
            best_score = 0
            
            for i, detection in enumerate(detections):
                if i not in unmatched_detections:
                    continue
                
                # Calculate IoU and feature similarity
                iou = self.calculate_iou(track['bbox'], detection['bbox'])
                feat_sim = self.calculate_feature_similarity(track['features'], detection['features'])
                
                # Combined score
                score = 0.4 * iou + 0.6 * feat_sim
                
                if score > best_score:
                    best_score = score
                    best_match_idx = i
            
            if best_match_idx != -1 and best_score > self.feature_threshold:
                # Update track
                detection = detections[best_match_idx]
                self.tracks[track_id].update({
                    'bbox': detection['bbox'],
                    'features': detection['features'],
                    'age': 0,
                    'hits': self.tracks[track_id]['hits'] + 1,
                    'center': detection['center']
                })
                self.tracks[track_id]['trail'].append(detection['center'])
                matched_tracks.append(track_id)
                unmatched_detections.remove(best_match_idx)
        
        # Create new tracks for unmatched detections
        for i in unmatched_detections:
            detection = detections[i]
            self.tracks[self.next_id] = {
                'bbox': detection['bbox'],
                'features': detection['features'],
                'age': 0,
                'hits': 1,
                'center': detection['center'],
                'trail': deque([detection['center']], maxlen=50)
            }
            self.next_id += 1
        
        # Age unmatched tracks
        for track_id in list(self.tracks.keys()):
            if track_id not in matched_tracks:
                self.tracks[track_id]['age'] += 1
                if self.tracks[track_id]['age'] > self.max_age:
                    del self.tracks[track_id]
        
        # Return confirmed tracks
        confirmed_tracks = []
        for track_id, track in self.tracks.items():
            if track['hits'] >= self.min_hits:
                track['id'] = track_id
                confirmed_tracks.append(track)
        
        return confirmed_tracks

class PersonTracker:
    def __init__(self, fairmot_model_path, car_ip="192.168.4.1"):
        self.yolo_model = None
        self.fairmot_tracker = FairMOTTracker(fairmot_model_path)
        self.tracked_person_id = None
        self.last_detection_time = None
        self.person_gone_threshold = 10.0  # 10 seconds
        self.person_locked = False
        self.frame_count = 0
        
        # Initialize smart car controller
        self.car_controller = SmartCarController(car_ip)
        self.car_connected = False
        
        # Add tracking parameters
        self.tracking_sensitivity = 50  # Pixels from center to trigger tracking
        self.tracking_enabled = True
        self.frame_dimensions = (640, 480)  # Default frame size
        
        # Add frame flipping option
        self.flip_frame = True  # Enable horizontal flipping by default
        
        # Setup models
        self.setup_models()
        
        # Test car connection
        self.test_car_connection()
        
    def test_car_connection(self):
        """Test connection to the smart car"""
        logger.info("Testing connection to smart car...")
        self.car_connected = self.car_controller.test_connection()
        if self.car_connected:
            logger.info("✅ Smart car connected successfully!")
            # Send initial stop command
            self.car_controller.emergency_stop()
        else:
            logger.warning("❌ Could not connect to smart car. Car control will be disabled.")
            logger.warning("Please ensure:")
            logger.warning("1. Smart car is powered on")
            logger.warning("2. Car is connected to WiFi network 'SLT_FIBRE'")
            logger.warning("3. Car IP address is correct (check router for assigned IP)")
        
    def setup_models(self):
        """Download and setup required models"""
        try:
            # Download YOLO11x-pose model
            logger.info("Loading YOLO11x-pose model...")
            self.yolo_model = YOLO('yolo11x-pose.pt')  # This will auto-download if not present
            logger.info("YOLO11x-pose model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error setting up models: {e}")
            raise
    
    def detect_raised_hand(self, keypoints, confidence_threshold=0.5):
        """
        Detect if person has raised hand (left or right) - Using working logic from main copy.py
        COCO pose keypoints indices:
        5: left shoulder, 6: right shoulder
        7: left elbow, 8: right elbow
        9: left wrist, 10: right wrist
        """
        if keypoints is None or len(keypoints) < 17:
            return False, None
        
        # Extract keypoints with confidence > threshold
        kpts = keypoints.reshape(-1, 3)  # [x, y, confidence]
        
        # Check if required keypoints are visible
        left_shoulder = kpts[5] if kpts[5][2] > confidence_threshold else None
        right_shoulder = kpts[6] if kpts[6][2] > confidence_threshold else None
        left_elbow = kpts[7] if kpts[7][2] > confidence_threshold else None
        right_elbow = kpts[8] if kpts[8][2] > confidence_threshold else None
        left_wrist = kpts[9] if kpts[9][2] > confidence_threshold else None
        right_wrist = kpts[10] if kpts[10][2] > confidence_threshold else None
        
        raised_hand = None
        
        # Check left hand raised - same logic as working main copy.py
        if (left_shoulder is not None and left_elbow is not None and 
            left_wrist is not None):
            if (left_wrist[1] < left_elbow[1] and 
                left_elbow[1] < left_shoulder[1]):
                raised_hand = "left"
                logger.info(f"🖐️ LEFT HAND DETECTED!")
        
        # Check right hand raised - same logic as working main copy.py
        if (right_shoulder is not None and right_elbow is not None and 
            right_wrist is not None):
            if (right_wrist[1] < right_elbow[1] and 
                right_elbow[1] < right_shoulder[1]):
                if raised_hand == "left":
                    raised_hand = "both"
                    logger.info(f"🖐️ BOTH HANDS DETECTED!")
                else:
                    raised_hand = "right"
                    logger.info(f"🖐️ RIGHT HAND DETECTED!")
        
        return raised_hand is not None, raised_hand
    
    def calculate_person_center(self, bbox):
        """Calculate center point of person bounding box"""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)
    
    def calculate_distance(self, point1, point2):
        """Calculate Euclidean distance between two points"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def draw_pose_keypoints(self, frame, keypoints, bbox):
        """Draw pose keypoints on frame"""
        if keypoints is None:
            return frame
        
        # COCO pose connections
        pose_connections = [
            (5, 6), (5, 7), (6, 8), (7, 9), (8, 10),  # Arms
            (5, 11), (6, 12), (11, 12),  # Torso
            (11, 13), (12, 14), (13, 15), (14, 16)  # Legs
        ]
        
        kpts = keypoints.reshape(-1, 3)
        
        # Draw keypoints
        for i, (x, y, conf) in enumerate(kpts):
            if conf > 0.3:  # Lower threshold to see more keypoints
                color = (0, 255, 0) if conf > 0.6 else (0, 255, 255)  # Green for high conf, yellow for low
                cv2.circle(frame, (int(x), int(y)), 4, color, -1)
                # Draw keypoint index for debugging
                cv2.putText(frame, str(i), (int(x)-10, int(y)-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        
        # Draw connections
        for connection in pose_connections:
            pt1_idx, pt2_idx = connection
            if (pt1_idx < len(kpts) and pt2_idx < len(kpts) and
                kpts[pt1_idx][2] > 0.5 and kpts[pt2_idx][2] > 0.5):
                pt1 = (int(kpts[pt1_idx][0]), int(kpts[pt1_idx][1]))
                pt2 = (int(kpts[pt2_idx][0]), int(kpts[pt2_idx][1]))
                cv2.line(frame, pt1, pt2, (255, 0, 0), 2)
        
        return frame
    
    def draw_tracking_trail(self, frame, trail, color=(0, 255, 255)):
        """Draw tracking trail on frame"""
        if len(trail) < 2:
            return frame
        
        # Draw trail points
        for i in range(len(trail) - 1):
            pt1 = (int(trail[i][0]), int(trail[i][1]))
            pt2 = (int(trail[i + 1][0]), int(trail[i + 1][1]))
            
            # Fade color based on age
            alpha = (i + 1) / len(trail)
            trail_color = tuple(int(c * alpha) for c in color)
            
            cv2.line(frame, pt1, pt2, trail_color, 2)
            cv2.circle(frame, pt2, 2, trail_color, -1)
        
        return frame
    
    def process_frame(self, frame):
        """Enhanced process_frame with person tracking and orientation adjustment"""
        self.frame_count += 1
        current_time = time.time()
        
        # Update frame dimensions
        self.frame_dimensions = (frame.shape[1], frame.shape[0])
        
        # Run YOLO detection
        results = self.yolo_model(frame, classes=[0])  # Class 0 is person
        
        if not results or len(results) == 0:
            # No detections - update tracker with empty list
            tracks = self.fairmot_tracker.update(frame, [])
            
            if self.person_locked and self.last_detection_time:
                time_since_detection = current_time - self.last_detection_time
                if time_since_detection > self.person_gone_threshold:
                    logger.info("Tracked person has been gone too long. Resetting tracking.")
                    self.person_locked = False
                    self.tracked_person_id = None
                    # Send stop command to car
                    if self.car_connected:
                        self.car_controller.emergency_stop()
            
            # No person to track, send center command
            if self.car_connected and self.tracking_enabled:
                self.car_controller.handle_person_tracking(
                    person_center=None,
                    frame_dimensions=self.frame_dimensions
                )
            
            return frame, [], []
        
        # Extract detections with raised hand detection
        detections = []
        for result in results:
            if result.boxes is not None:
                for i, box in enumerate(result.boxes):
                    bbox = box.xyxy[0].cpu().numpy().astype(int)
                    conf = box.conf[0].cpu().numpy()
                    
                    if conf > 0.5:  # Confidence threshold
                        center = self.calculate_person_center(bbox)
                        
                        # Get keypoints if available
                        keypoints = None
                        has_raised_hand = False
                        hand_side = None
                        
                        if hasattr(result, 'keypoints') and result.keypoints is not None:
                            if i < len(result.keypoints.data):
                                keypoints = result.keypoints.data[i].cpu().numpy()
                                has_raised_hand, hand_side = self.detect_raised_hand(keypoints)
                                if has_raised_hand:
                                    logger.info(f"✋ Hand gesture detected: {hand_side}")
                        
                        detections.append({
                            'bbox': bbox,
                            'confidence': conf,
                            'center': center,
                            'keypoints': keypoints,
                            'has_raised_hand': has_raised_hand,
                            'hand_side': hand_side
                        })
        
        if not detections:
            tracks = self.fairmot_tracker.update(frame, [])
            if self.car_connected and self.tracking_enabled:
                self.car_controller.handle_person_tracking(
                    person_center=None,
                    frame_dimensions=self.frame_dimensions
                )
            return frame, tracks, detections
        
        # Update FairMOT tracker
        tracks = self.fairmot_tracker.update(frame, detections)
        
        # Add raised hand information to tracks
        for track in tracks:
            track['has_raised_hand'] = False
            track['hand_side'] = None
            track['keypoints'] = None
            
            # Find corresponding detection
            for detection in detections:
                if self.calculate_distance(track['center'], detection['center']) < 50:
                    track['has_raised_hand'] = detection['has_raised_hand']
                    track['hand_side'] = detection['hand_side']
                    track['keypoints'] = detection['keypoints']
                    break
        
        # If no person is locked, find the first person with raised hand
        if not self.person_locked:
            for track in tracks:
                if track['has_raised_hand']:
                    self.tracked_person_id = track['id']
                    self.person_locked = True
                    self.last_detection_time = current_time
                    logger.info(f"🔒 Locked tracking on person {self.tracked_person_id} with {track['hand_side']} hand raised")
                    break
        
        # If person is locked, filter tracks to show only tracked person
        if self.person_locked:
            tracked_person_found = False
            filtered_tracks = []
            
            for track in tracks:
                if track['id'] == self.tracked_person_id:
                    filtered_tracks.append(track)
                    tracked_person_found = True
                    self.last_detection_time = current_time
                    
                    # Send car command with person tracking
                    if self.car_connected and self.tracking_enabled:
                        self.car_controller.handle_person_tracking(
                            person_center=track['center'],
                            frame_dimensions=self.frame_dimensions,
                            has_raised_hand=track['has_raised_hand'],
                            hand_side=track['hand_side']
                        )
                    break
            
            if not tracked_person_found:
                time_since_detection = current_time - self.last_detection_time if self.last_detection_time else 0
                if time_since_detection > self.person_gone_threshold:
                    logger.info("Tracked person lost. Resetting tracking.")
                    self.person_locked = False
                    self.tracked_person_id = None
                    # Send stop command to car
                    if self.car_connected:
                        self.car_controller.emergency_stop()
            
            tracks = filtered_tracks
        
        # If no person is locked and no raised hands detected, handle tracking
        if not self.person_locked and self.car_connected and self.tracking_enabled:
            # Find the closest person to center for tracking (even without raised hand)
            if tracks:
                frame_center_x = self.frame_dimensions[0] // 2
                closest_track = min(tracks, key=lambda t: abs(t['center'][0] - frame_center_x))
                
                self.car_controller.handle_person_tracking(
                    person_center=closest_track['center'],
                    frame_dimensions=self.frame_dimensions,
                    has_raised_hand=False
                )
            else:
                self.car_controller.handle_person_tracking(
                    person_center=None,
                    frame_dimensions=self.frame_dimensions
                )
        
        return frame, tracks, detections
    
    def draw_detections(self, frame, tracks):
        """Enhanced draw_detections with tracking indicators"""
        # Draw frame center line for tracking reference
        if self.tracking_enabled:
            frame_center_x = frame.shape[1] // 2
            cv2.line(frame, (frame_center_x, 0), (frame_center_x, frame.shape[0]), (255, 255, 255), 1)
            
            # Draw tracking zone
            threshold = self.car_controller.frame_center_threshold if self.car_connected else 50
            left_bound = frame_center_x - threshold
            right_bound = frame_center_x + threshold
            
            cv2.line(frame, (left_bound, 0), (left_bound, frame.shape[0]), (0, 255, 255), 1)
            cv2.line(frame, (right_bound, 0), (right_bound, frame.shape[0]), (0, 255, 255), 1)
            
            # Add tracking zone label
            cv2.putText(frame, "TRACKING ZONE", (left_bound, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        for track in tracks:
            bbox = track['bbox']
            track_id = track['id']
            trail = track['trail']
            has_raised_hand = track.get('has_raised_hand', False)
            hand_side = track.get('hand_side', None)
            keypoints = track.get('keypoints', None)
            person_center = track['center']
            
            # Draw tracking trail
            trail_color = (0, 255, 255) if not has_raised_hand else (0, 255, 0)
            frame = self.draw_tracking_trail(frame, trail, trail_color)
            
            # Draw bounding box with tracking status
            x1, y1, x2, y2 = bbox
            if has_raised_hand:
                color = (0, 255, 0)  # Green for raised hand
                thickness = 3
            elif self.person_locked and track_id == self.tracked_person_id:
                color = (255, 0, 0)  # Blue for tracked person
                thickness = 3
            else:
                color = (0, 255, 255)  # Yellow for regular detection
                thickness = 2
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            
            # Draw person center point
            cv2.circle(frame, person_center, 5, color, -1)
            
            # Draw tracking direction indicator
            if self.tracking_enabled and self.person_locked and track_id == self.tracked_person_id:
                frame_center_x = frame.shape[1] // 2
                offset_x = person_center[0] - frame_center_x
                
                if abs(offset_x) > (self.car_controller.frame_center_threshold if self.car_connected else 50):
                    # Draw arrow indicating tracking direction
                    if offset_x < 0:
                        # Person is left, car should turn left
                        arrow_start = (person_center[0] + 30, person_center[1])
                        arrow_end = (person_center[0] + 60, person_center[1])
                        cv2.arrowedLine(frame, arrow_start, arrow_end, (255, 0, 255), 3)
                        cv2.putText(frame, "CAR TURNING LEFT", (x1, y2 + 45), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                    else:
                        # Person is right, car should turn right
                        arrow_start = (person_center[0] - 30, person_center[1])
                        arrow_end = (person_center[0] - 60, person_center[1])
                        cv2.arrowedLine(frame, arrow_start, arrow_end, (255, 0, 255), 3)
                        cv2.putText(frame, "CAR TURNING RIGHT", (x1, y2 + 45), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                else:
                    cv2.putText(frame, "CENTERED", (x1, y2 + 45), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Draw pose keypoints if available
            if keypoints is not None:
                frame = self.draw_pose_keypoints(frame, keypoints, bbox)
            
            # Create comprehensive label
            label_parts = [f"ID: {track_id}"]
            
            if has_raised_hand and hand_side:
                label_parts.append(f"{hand_side.upper()} HAND")
                
            if self.person_locked and track_id == self.tracked_person_id:
                label_parts.append("TRACKED")
            
            label = " - ".join(label_parts)
            
            # Draw label with background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Draw raised hand indicator
            if has_raised_hand:
                cv2.putText(frame, f"🖐️ {hand_side.upper()}", (x1, y2 + 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        
        return frame
    
    def run_webcam(self):
        """Enhanced webcam run with tracking controls"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            logger.error("Cannot open webcam")
            return
        
        logger.info("Starting enhanced smart car tracking system...")
        logger.info("🖐️ LEFT hand = FORWARD | RIGHT hand = STOP")
        logger.info("🎯 Car will automatically adjust orientation to track person")
        logger.info("🔄 Frame mirroring enabled for natural interaction")
        logger.info("Press 't' to toggle tracking, 's' to adjust sensitivity, 'f' to toggle mirror")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Flip frame horizontally for mirror effect
                if self.flip_frame:
                    frame = cv2.flip(frame, 1)
                
                # Process frame with enhanced tracking
                processed_frame, tracks, detections = self.process_frame(frame)
                
                # Draw enhanced tracking information
                output_frame = self.draw_detections(processed_frame, tracks)
                
                # Draw main status information
                status_text = "🔒 TRACKING LOCKED" if self.person_locked else "🔍 SEARCHING FOR RAISED HAND"
                status_color = (0, 255, 0) if self.person_locked else (0, 0, 255)
                cv2.putText(output_frame, status_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
                
                # Show car connection and tracking status
                car_status = "🚗 CAR CONNECTED" if self.car_connected else "❌ CAR DISCONNECTED"
                car_color = (0, 255, 0) if self.car_connected else (0, 0, 255)
                cv2.putText(output_frame, car_status, (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, car_color, 2)
                
                tracking_status = f"🎯 TRACKING: {'ON' if self.tracking_enabled else 'OFF'}"
                tracking_color = (0, 255, 0) if self.tracking_enabled else (0, 0, 255)
                cv2.putText(output_frame, tracking_status, (10, 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, tracking_color, 2)
                
                # Show tracking sensitivity
                if self.car_connected:
                    sensitivity_text = f"Sensitivity: {self.car_controller.frame_center_threshold}px"
                    cv2.putText(output_frame, sensitivity_text, (10, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Show enhanced control instructions
                cv2.putText(output_frame, "LEFT=FORWARD | RIGHT=STOP | CAR AUTO-TRACKS PERSON", 
                           (10, output_frame.shape[0] - 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(output_frame, "q=quit | r=reset | t=toggle tracking | s=sensitivity | f=flip", 
                           (10, output_frame.shape[0] - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Show flip status
                flip_status = f"🔄 MIRROR: {'ON' if self.flip_frame else 'OFF'}"
                flip_color = (0, 255, 0) if self.flip_frame else (0, 0, 255)
                cv2.putText(output_frame, flip_status, (10, output_frame.shape[0] - 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, flip_color, 2)
                
                # Display frame
                cv2.imshow('Smart Car Hand Control with Auto-Tracking', output_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    logger.info("Resetting tracking system...")
                    self.person_locked = False
                    self.tracked_person_id = None
                    self.last_detection_time = None
                    if self.car_connected:
                        self.car_controller.emergency_stop()
                elif key == ord('t'):
                    # Toggle tracking
                    self.tracking_enabled = not self.tracking_enabled
                    if self.car_connected:
                        self.car_controller.enable_tracking(self.tracking_enabled)
                    logger.info(f"Person tracking {'enabled' if self.tracking_enabled else 'disabled'}")
                elif key == ord('s'):
                    # Adjust sensitivity
                    if self.car_connected:
                        current = self.car_controller.frame_center_threshold
                        new_sensitivity = 30 if current >= 50 else current + 20
                        self.car_controller.set_tracking_sensitivity(new_sensitivity)
                        logger.info(f"Tracking sensitivity adjusted to {new_sensitivity} pixels")
                elif key == ord('c'):
                    # Test car connection
                    logger.info("Testing car connection...")
                    self.test_car_connection()
                elif key == ord('f'):
                    # Toggle frame flipping
                    self.flip_frame = not self.flip_frame
                    logger.info(f"Frame mirroring {'enabled' if self.flip_frame else 'disabled'}")
        
        finally:
            # Ensure car stops when exiting
            if self.car_connected:
                logger.info("Sending final stop command to car...")
                self.car_controller.emergency_stop()
            
            cap.release()
            cv2.destroyAllWindows()
    
    def run_video(self, video_path):
        """Run the tracking system with video file input"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            logger.error(f"Cannot open video file: {video_path}")
            return
        
        logger.info(f"Processing video: {video_path}")
        logger.info("🖐️ System will detect raised hands and control car")
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Flip frame horizontally for mirror effect
                if self.flip_frame:
                    frame = cv2.flip(frame, 1)
                
                # Process frame
                processed_frame, tracks, detections = self.process_frame(frame)
                
                # Draw tracking information
                output_frame = self.draw_detections(processed_frame, tracks)
                
                # Draw status information
                status_text = "🔒 TRACKING LOCKED" if self.person_locked else "🔍 SEARCHING FOR RAISED HAND"
                status_color = (0, 255, 0) if self.person_locked else (0, 0, 255)
                cv2.putText(output_frame, status_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)
                
                # Show car connection status
                car_status = "🚗 CAR CONNECTED" if self.car_connected else "❌ CAR DISCONNECTED"
                car_color = (0, 255, 0) if self.car_connected else (0, 0, 255)
                cv2.putText(output_frame, car_status, (10, 70), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, car_color, 2)
                
                # Show raised hand detection status
                if not self.person_locked:
                    for i, detection in enumerate(detections):
                        if detection['has_raised_hand']:
                            hand_text = f"Person {i+1}: {detection['hand_side']} hand raised"
                            cv2.putText(output_frame, hand_text, (10, 110 + i*30), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                
                if self.person_locked:
                    tracking_text = f"Tracking Person ID: {self.tracked_person_id}"
                    cv2.putText(output_frame, tracking_text, (10, 110), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                
                # Show control instructions
                cv2.putText(output_frame, "LEFT HAND = FORWARD | RIGHT HAND = STOP", 
                           (10, output_frame.shape[0] - 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(output_frame, "Press 'q' to quit | 'r' to reset | 'f' to toggle mirror", 
                           (10, output_frame.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Show flip status
                flip_status = f"🔄 MIRROR: {'ON' if self.flip_frame else 'OFF'}"
                flip_color = (0, 255, 0) if self.flip_frame else (0, 0, 255)
                cv2.putText(output_frame, flip_status, (10, output_frame.shape[0] - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, flip_color, 2)
                
                # Display frame
                cv2.imshow('Smart Car Hand Control System', output_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    logger.info("Resetting tracking system...")
                    self.person_locked = False
                    self.tracked_person_id = None
                    self.last_detection_time = None
                    if self.car_connected:
                        self.car_controller.emergency_stop()
                elif key == ord('f'):
                    # Toggle frame flipping
                    self.flip_frame = not self.flip_frame
                    logger.info(f"Frame mirroring {'enabled' if self.flip_frame else 'disabled'}")
        
        finally:
            # Ensure car stops when exiting
            if self.car_connected:
                logger.info("Sending final stop command to car...")
                self.car_controller.emergency_stop()
            
            cap.release()
            cv2.destroyAllWindows()

def main():
    """Main function to run the person tracking system with smart car integration"""
    try:
        # Path to FairMOT pretrained model
        fairmot_model_path = r"C:\Users\menuk\Desktop\vision-guided smart car system\hrnetv2_w32_imagenet_pretrained.pth"
        
        # Initialize tracker with car integration
        # ESP32 connected to SLT_FIBRE network with IP: 192.168.1.112
        tracker = PersonTracker(fairmot_model_path, car_ip="192.168.1.112")
        
        # Choose input source
        print("Smart Car Hand Control System")
        print("=============================")
        print("Control Instructions:")
        print("- Raise LEFT hand: Car moves FORWARD")
        print("- Raise RIGHT hand: Car STOPS")
        print("- No hands raised: Car STOPS")
        print("")
        print("Choose input source:")
        print("1. Webcam")
        print("2. Video file")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            tracker.run_webcam()
        elif choice == "2":
            video_path = input("Enter video file path: ").strip()
            tracker.run_video(video_path)
        else:
            print("Invalid choice. Using webcam by default.")
            tracker.run_webcam()
            
    except KeyboardInterrupt:
        logger.info("System interrupted by user")
    except Exception as e:
        logger.error(f"Error running tracker: {e}")

if __name__ == "__main__":
    main()
