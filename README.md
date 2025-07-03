# 🚗 Vision-Guided Smart Car System

<div align="center">

![Smart Car](https://img.shields.io/badge/Smart%20Car-ESP32-blue)
![Computer Vision](https://img.shields.io/badge/Computer%20Vision-YOLO11-green)
![Hand Gesture](https://img.shields.io/badge/Hand%20Gesture-Recognition-orange)
![Person Tracking](https://img.shields.io/badge/Person-Tracking-red)
![Real Time](https://img.shields.io/badge/Real%20Time-Processing-yellow)

**An intelligent autonomous car system that responds to hand gestures and actively tracks people using advanced computer vision**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Hardware](#-hardware) • [Contributing](#-contributing)

</div>

---

## 🌟 Features

### 🖐️ **Hand Gesture Control**
- **Left Hand Raised**: Car moves forward
- **Right Hand Raised**: Car stops immediately
- **Both Hands**: Emergency stop
- Real-time gesture recognition using YOLO11-pose

### 🎯 **Intelligent Person Tracking**
- **Auto-Orient**: Car automatically adjusts its position to keep the tracked person centered
- **Person Lock**: Locks onto the first person who raises their hand
- **Trail Visualization**: Shows movement history with colored trails
- **Smart Recovery**: Handles person loss and re-detection

### 📹 **Advanced Computer Vision**
- **YOLO11x-pose**: State-of-the-art pose estimation
- **FairMOT Tracking**: Multi-object tracking with feature extraction
- **Real-time Processing**: Optimized for live camera feeds
- **Visual Feedback**: Rich on-screen indicators and status displays

### 🚗 **Smart Car Features**
- **ESP32-based**: WiFi-enabled microcontroller
- **4-Motor Drive**: Precise movement control
- **HTTP API**: RESTful communication
- **Emergency Stop**: Safety-first design

---

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- OpenCV 4.5+
- PyTorch 1.9+
- ESP32 with WiFi capability

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/vision-guided-smart-car.git
cd vision-guided-smart-car
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Download Models
The system will automatically download required models on first run:
- `yolo11x-pose.pt` - YOLO11 pose estimation model
- `hrnetv2_w32_imagenet_pretrained.pth` - FairMOT tracking model

### 4. Hardware Setup
1. Flash `smartcar.cpp` to your ESP32
2. Connect motors to designated pins
3. Connect to WiFi network
4. Note the assigned IP address

---

## 🚀 Usage

### Basic Operation
```python
python main_with_car.py
```

### Configuration
1. **Set Car IP**: Update the IP address in `main_with_car.py`
```python
tracker = PersonTracker(fairmot_model_path, car_ip="192.168.1.112")
```

2. **Choose Input Source**:
   - Option 1: Webcam (default)
   - Option 2: Video file

### Interactive Controls
| Key | Function |
|-----|----------|
| `q` | Quit application |
| `r` | Reset tracking system |
| `t` | Toggle person tracking on/off |
| `s` | Adjust tracking sensitivity |
| `c` | Test car connection |

---

## 🔧 Hardware Requirements

### Smart Car Components
- **Microcontroller**: ESP32 DevKit
- **Motors**: 4x DC motors with motor drivers
- **Power**: 7.4V LiPo battery
- **WiFi**: Built-in ESP32 WiFi

### Pin Configuration
```cpp
Motor Pins:
- Front Right: IN1=14, IN2=12
- Back Right:  IN1=13, IN2=4
- Front Left:  IN1=27, IN2=26
- Back Left:   IN1=25, IN2=33
```

### Computer Requirements
- **Camera**: USB webcam or laptop camera
- **CPU**: Intel i5 or equivalent (for real-time processing)
- **RAM**: 8GB minimum
- **GPU**: Optional (CUDA-compatible for faster inference)

---

## 📁 Project Structure

```
vision-guided-smart-car/
├── main_with_car.py           # Main application
├── car_controller.py          # Smart car communication
├── smartcar.cpp              # ESP32 firmware
├── requirements.txt          # Python dependencies
├── yolo11x-pose.pt          # YOLO11 pose model
├── hrnetv2_w32_imagenet_pretrained.pth  # FairMOT model
└── README.md                # Project documentation
```

---

## 🧠 How It Works

### 1. **Person Detection**
- YOLO11-pose detects people and extracts keypoints
- Identifies hand positions (wrist, elbow, shoulder)
- Analyzes vertical relationships to detect raised hands

### 2. **Hand Gesture Recognition**
```python
# Hand detection logic
if wrist_y < elbow_y < shoulder_y:
    hand_raised = True
```

### 3. **Person Tracking**
- FairMOT tracker maintains person identity across frames
- Locks onto first person who raises their hand
- Calculates person's position relative to frame center

### 4. **Car Control**
- HTTP POST requests sent to ESP32
- Gesture commands: forward/stop
- Tracking commands: turn left/right/center

### 5. **Auto-Orientation**
```python
# Tracking logic
if person_x < center_x - threshold:
    send_command("track_left")
elif person_x > center_x + threshold:
    send_command("track_right")
else:
    send_command("track_center")
```

---

## 🎯 Key Features Explained

### **Smart Person Locking**
- System waits for a person to raise their hand before tracking
- Once locked, follows only that specific person
- Automatic unlock after 10 seconds of person absence

### **Dual Control System**
- **Hand Gestures**: Control car movement (forward/stop)
- **Position Tracking**: Control car orientation (left/right/center)
- Both systems work simultaneously for smooth operation

### **Visual Feedback**
- Real-time status indicators
- Tracking zone visualization
- Movement direction arrows
- Connection status displays

### **Safety Features**
- Emergency stop on connection loss
- Automatic reset on person loss
- Configurable tracking sensitivity
- Manual override controls

---

## 🔧 Troubleshooting

### Connection Issues
```bash
# Check car connection
ping 192.168.1.112

# Verify WiFi network
# Ensure both computer and ESP32 are on same network
```

### Performance Optimization
```python
# Reduce model size for better performance
self.yolo_model = YOLO('yolo11n-pose.pt')  # Nano version

# Adjust confidence threshold
if conf > 0.3:  # Lower threshold for better detection
```

### Common Issues
1. **Car not responding**: Check IP address and WiFi connection
2. **Hand detection failing**: Ensure good lighting and clear view
3. **Tracking lag**: Reduce frame size or use faster model
4. **Person loss**: Adjust tracking sensitivity with 's' key

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Areas for Improvement
- [ ] Voice control integration
- [ ] Mobile app interface
- [ ] Multi-person tracking
- [ ] Obstacle detection
- [ ] Route planning

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Ultralytics** for YOLO11 implementation
- **FairMOT** team for multi-object tracking
- **ESP32** community for hardware support
- **OpenCV** for computer vision tools

---

<div align="center">

**⭐ Star this repository if you found it helpful!**

Made with ❤️ by [Your Name]

</div>
