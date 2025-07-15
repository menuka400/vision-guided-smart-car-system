import cv2
import numpy as np
import time
import os
import torch
from ultralytics import YOLO
import logging

# Import the smart car controller
from car_controller import SmartCarController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GestureDetector:
    def __init__(self, car_ip="192.168.1.112"):
        self.yolo_model = None
        self.frame_dimensions = (640, 480)
        
        # Initialize smart car controller
        self.car_controller = SmartCarController(car_ip)
        self.car_connected = False
        
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
            logger.warning("2. Car is connected to WiFi network")
            logger.warning("3. Car IP address is correct")
        
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
                logger.info("🖐️ LEFT HAND DETECTED!")
        
        # Check right hand raised - same logic as working main copy.py
        if (right_shoulder is not None and right_elbow is not None and 
            right_wrist is not None):
            if (right_wrist[1] < right_elbow[1] and 
                right_elbow[1] < right_shoulder[1]):
                if raised_hand == "left":
                    raised_hand = "both"
                    logger.info("🖐️ BOTH HANDS DETECTED!")
                else:
                    raised_hand = "right"
                    logger.info("🖐️ RIGHT HAND DETECTED!")
        
        return raised_hand is not None, raised_hand
    
    def draw_pose_keypoints(self, frame, keypoints, bbox):
        """Draw pose keypoints on frame"""
        if keypoints is None:
            return
            
        # Draw keypoint connections
        connections = [
            (5, 7), (7, 9),   # Left arm
            (6, 8), (8, 10),  # Right arm
            (5, 6),           # Shoulders
            (11, 13), (13, 15),  # Left leg
            (12, 14), (14, 16),  # Right leg
            (11, 12),         # Hips
            (5, 11), (6, 12)  # Spine
        ]
        
        # Draw bounding box
        x1, y1, x2, y2 = map(int, bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw keypoints and connections
        for connection in connections:
            pt1 = tuple(map(int, keypoints[connection[0]][:2]))
            pt2 = tuple(map(int, keypoints[connection[1]][:2]))
            cv2.line(frame, pt1, pt2, (0, 255, 0), 2)
            
        for kp in keypoints:
            x, y = map(int, kp[:2])
            cv2.circle(frame, (x, y), 4, (255, 0, 0), -1)
    
    def process_frame(self, frame):
        """Process a single frame"""
        if frame is None:
            return frame
            
        # Update frame dimensions
        self.frame_dimensions = (frame.shape[1], frame.shape[0])
        
        # Flip frame if enabled
        if self.flip_frame:
            frame = cv2.flip(frame, 1)
        
        # Run YOLO pose detection
        results = self.yolo_model(frame, verbose=False)
        
        # Process first detected person
        has_raised_hand = False
        hand_side = None
        
        for result in results:
            boxes = result.boxes.cpu().numpy()
            keypoints = result.keypoints.cpu().numpy()
            
            if len(boxes) > 0:
                # Get first person detection
                box = boxes[0]
                kpts = keypoints[0]
                
                if box.conf[0] >= 0.5:  # Confidence threshold
                    # Get bounding box
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Check for raised hands
                    has_raised_hand, hand_side = self.detect_raised_hand(kpts.data[0])
                    
                    # Draw visualization
                    self.draw_pose_keypoints(frame, kpts.data[0], (x1, y1, x2, y2))
                    
                    # Send commands to car if connected
                    if self.car_connected:
                        self.car_controller.handle_gesture(has_raised_hand, hand_side)
                    
                    break  # Only process first person
        
        # Draw status text with movement direction
        if has_raised_hand and hand_side:
            if hand_side == "left":
                status = "✋ LEFT hand - FORWARD"
            elif hand_side == "right":
                status = "✋ RIGHT hand - BACKWARD"
            elif hand_side == "both":
                status = "✋ BOTH hands - STOP"
            else:
                status = "✋ Hand detected"
        else:
            status = "No hand gesture - STOPPED"
        
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        return frame
    
    def run_webcam(self):
        """Run detection on webcam feed"""
        # Initialize webcam
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_dimensions[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_dimensions[1])
        
        logger.info("Starting webcam capture...")
        logger.info("Press 'q' to quit")
        
        try:
            while True:
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    logger.error("Failed to grab frame")
                    break
                
                # Process frame
                output_frame = self.process_frame(frame)
                
                # Display frame
                cv2.imshow('Smart Car Vision System', output_frame)
                
                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("User requested quit")
                    break
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            
        finally:
            # Clean up
            logger.info("Cleaning up...")
            if self.car_connected:
                self.car_controller.emergency_stop()
            cap.release()
            cv2.destroyAllWindows()
    
    def run_video(self, video_path):
        """Run detection on video file"""
        # Open video file
        cap = cv2.VideoCapture(video_path)
        
        logger.info(f"Starting video processing: {video_path}")
        logger.info("Press 'q' to quit")
        
        try:
            while cap.isOpened():
                # Read frame
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Process frame
                output_frame = self.process_frame(frame)
                
                # Display frame
                cv2.imshow('Smart Car Vision System', output_frame)
                
                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("User requested quit")
                    break
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            
        finally:
            # Clean up
            logger.info("Cleaning up...")
            if self.car_connected:
                self.car_controller.emergency_stop()
            cap.release()
            cv2.destroyAllWindows()

def main():
    """Main entry point"""
    detector = GestureDetector()
    detector.run_webcam()

if __name__ == "__main__":
    main()
