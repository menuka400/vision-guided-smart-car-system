/*
 * SMART CAR MOTOR DIRECTION CALIBRATION
 * 
 * If any motor rotates backwards during the startup test:
 * 1. Find the motor number from the test output
 * 2. Set motorDirectionCorrection[motor_number] = -1
 * 
 * Example: If FRONT_RIGHT_MOTOR (motor 0) rotates backwards:
 * Change: int motorDirectionCorrection[4] = {1, 1, 1, 1};
 * To:     int motorDirectionCorrection[4] = {-1, 1, 1, 1};
 * 
 * Motor Numbers:
 * 0 = FRONT_RIGHT_MOTOR
 * 1 = BACK_RIGHT_MOTOR  
 * 2 = FRONT_LEFT_MOTOR
 * 3 = BACK_LEFT_MOTOR
 */

#include <Arduino.h>
#ifdef ESP32
#include <WiFi.h>
#include <AsyncTCP.h>
#elif defined(ESP8266)
#include <ESP8266WiFi.h>
#include <ESPAsyncTCP.h>
#endif
#include <ESPAsyncWebServer.h>

#define UP 1
#define DOWN 2
#define LEFT 3
#define RIGHT 4
#define UP_LEFT 5
#define UP_RIGHT 6
#define DOWN_LEFT 7
#define DOWN_RIGHT 8
#define TURN_LEFT 9
#define TURN_RIGHT 10
#define STOP 0

// Hand gesture commands
#define HAND_LEFT_RAISED 11
#define HAND_RIGHT_RAISED 12
#define HAND_BOTH_RAISED 13
#define HAND_NONE_RAISED 14

// Add new movement commands for tracking
#define TRACK_LEFT 15
#define TRACK_RIGHT 16
#define TRACK_CENTER 17

#define FRONT_RIGHT_MOTOR 0
#define BACK_RIGHT_MOTOR 1
#define FRONT_LEFT_MOTOR 2
#define BACK_LEFT_MOTOR 3

#define FORWARD 1
#define BACKWARD -1

// PWM settings for motor speed control
#define MAX_SPEED 255
#define PWM_FREQUENCY 1000
#define PWM_RESOLUTION 8

struct MOTOR_PINS
{
  int pinIN1;
  int pinIN2;    
};

// Updated motor pin configuration
std::vector<MOTOR_PINS> motorPins = 
{
  {16, 17},  // FRONT_RIGHT_MOTOR
  {18, 19},  // BACK_RIGHT_MOTOR
  {27, 26},  // FRONT_LEFT_MOTOR
  {25, 33},  // BACK_LEFT_MOTOR
};

// Motor direction correction - set to -1 for motors that are wired backwards
// Test each motor individually and set -1 for any that rotate backwards
int motorDirectionCorrection[4] = {-1, 1, 1, 1};  // Motor 0 (FRONT_RIGHT) is reversed

const char* ssid     = "SLT_FIBRE";
const char* password = "abcd1234";

AsyncWebServer server(80);
AsyncWebSocket ws("/ws");

const char* htmlHomePage PROGMEM = R"HTMLHOMEPAGE(
<!DOCTYPE html>
<html>
  <head>
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <style>
    .arrows {
      font-size:70px;
      color:red;
    }
    .circularArrows {
      font-size:80px;
      color:blue;
    }
    td {
      background-color:black;
      border-radius:25%;
      box-shadow: 5px 5px #888888;
    }
    td:active {
      transform: translate(5px,5px);
      box-shadow: none; 
    }

    .noselect {
      -webkit-touch-callout: none;
        -webkit-user-select: none;
         -khtml-user-select: none;
           -moz-user-select: none;
            -ms-user-select: none;
                user-select: none;
    }
    </style>
  </head>
  <body class="noselect" align="center" style="background-color:white">
     
    <h1 style="color: teal;text-align:center;">Hash Include Electronics</h1>
    <h2 style="color: teal;text-align:center;">Wi-Fi &#128663; Control</h2>
    
    <table id="mainTable" style="width:400px;margin:auto;table-layout:fixed" CELLSPACING=10>
      <tr>
        <td ontouchstart='onTouchStartAndEnd("5")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#11017;</span></td>
        <td ontouchstart='onTouchStartAndEnd("1")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#8679;</span></td>
        <td ontouchstart='onTouchStartAndEnd("6")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#11016;</span></td>
      </tr>
      
      <tr>
        <td ontouchstart='onTouchStartAndEnd("3")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#8678;</span></td>
        <td></td>    
        <td ontouchstart='onTouchStartAndEnd("4")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#8680;</span></td>
      </tr>
      
      <tr>
        <td ontouchstart='onTouchStartAndEnd("7")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#11019;</span></td>
        <td ontouchstart='onTouchStartAndEnd("2")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#8681;</span></td>
        <td ontouchstart='onTouchStartAndEnd("8")' ontouchend='onTouchStartAndEnd("0")'><span class="arrows" >&#11018;</span></td>
      </tr>
    
      <tr>
        <td ontouchstart='onTouchStartAndEnd("9")' ontouchend='onTouchStartAndEnd("0")'><span class="circularArrows" >&#8634;</span></td>
        <td style="background-color:white;box-shadow:none"></td>
        <td ontouchstart='onTouchStartAndEnd("10")' ontouchend='onTouchStartAndEnd("0")'><span class="circularArrows" >&#8635;</span></td>
      </tr>
    </table>

    <script>
      var webSocketUrl = "ws:\/\/" + window.location.hostname + "/ws";
      var websocket;
      
      function initWebSocket() 
      {
        websocket = new WebSocket(webSocketUrl);
        websocket.onopen    = function(event){};
        websocket.onclose   = function(event){setTimeout(initWebSocket, 2000);};
        websocket.onmessage = function(event){};
      }

      function onTouchStartAndEnd(value) 
      {
        websocket.send(value);
      }
          
      window.onload = initWebSocket;
      document.getElementById("mainTable").addEventListener("touchend", function(event){
        event.preventDefault()
      });      
    </script>
    
  </body>
</html> 

)HTMLHOMEPAGE";

void rotateMotor(int motorNumber, int motorDirection)
{
  // Apply motor direction correction
  int correctedDirection = motorDirection * motorDirectionCorrection[motorNumber];
  
  if (correctedDirection == FORWARD)
  {
    ledcWrite(motorNumber * 2, MAX_SPEED);     // pinIN1 at max speed
    ledcWrite(motorNumber * 2 + 1, 0);        // pinIN2 at 0
  }
  else if (correctedDirection == BACKWARD)
  {
    ledcWrite(motorNumber * 2, 0);            // pinIN1 at 0
    ledcWrite(motorNumber * 2 + 1, MAX_SPEED); // pinIN2 at max speed
  }
  else
  {
    ledcWrite(motorNumber * 2, 0);            // pinIN1 at 0
    ledcWrite(motorNumber * 2 + 1, 0);        // pinIN2 at 0
  }
}

void processCarMovement(String inputValue)
{
  Serial.printf("Got value as %s %d\n", inputValue.c_str(), inputValue.toInt());  
  switch(inputValue.toInt())
  {
    case UP:
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);                  
      break;

    case DOWN:
      rotateMotor(FRONT_RIGHT_MOTOR, BACKWARD);
      rotateMotor(BACK_RIGHT_MOTOR, BACKWARD);
      rotateMotor(FRONT_LEFT_MOTOR, BACKWARD);
      rotateMotor(BACK_LEFT_MOTOR, BACKWARD);   
      break;

    case LEFT:
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, BACKWARD);
      rotateMotor(FRONT_LEFT_MOTOR, BACKWARD);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);   
      break;

    case RIGHT:
      rotateMotor(FRONT_RIGHT_MOTOR, BACKWARD);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, BACKWARD);  
      break;

    case UP_LEFT:
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);  
      break;

    case UP_RIGHT:
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, STOP);  
      break;

    case DOWN_LEFT:
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, BACKWARD);
      rotateMotor(FRONT_LEFT_MOTOR, BACKWARD);
      rotateMotor(BACK_LEFT_MOTOR, STOP);   
      break;

    case DOWN_RIGHT:
      rotateMotor(FRONT_RIGHT_MOTOR, BACKWARD);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, BACKWARD);   
      break;

    case TURN_LEFT:
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, BACKWARD);
      rotateMotor(BACK_LEFT_MOTOR, BACKWARD);  
      break;

    case TURN_RIGHT:
      rotateMotor(FRONT_RIGHT_MOTOR, BACKWARD);
      rotateMotor(BACK_RIGHT_MOTOR, BACKWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);   
      break;

    // Hand gesture controls
    case HAND_LEFT_RAISED:
      Serial.println("Left hand raised - Moving forward");
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);
      break;

    case HAND_RIGHT_RAISED:
      Serial.println("Right hand raised - Stopping");
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, STOP);
      break;

    case HAND_BOTH_RAISED:
      Serial.println("Both hands raised - Stopping");
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, STOP);
      break;

    case HAND_NONE_RAISED:
      Serial.println("No hands raised - Stopping");
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, STOP);
      break;

    // Add these new cases in the processCarMovement switch statement
    case TRACK_LEFT:
      Serial.println("Tracking left - adjusting car orientation");
      rotateMotor(FRONT_RIGHT_MOTOR, FORWARD);
      rotateMotor(BACK_RIGHT_MOTOR, FORWARD);
      rotateMotor(FRONT_LEFT_MOTOR, BACKWARD);
      rotateMotor(BACK_LEFT_MOTOR, BACKWARD);
      break;

    case TRACK_RIGHT:
      Serial.println("Tracking right - adjusting car orientation");
      rotateMotor(FRONT_RIGHT_MOTOR, BACKWARD);
      rotateMotor(BACK_RIGHT_MOTOR, BACKWARD);
      rotateMotor(FRONT_LEFT_MOTOR, FORWARD);
      rotateMotor(BACK_LEFT_MOTOR, FORWARD);
      break;

    case TRACK_CENTER:
      Serial.println("Target centered - stopping orientation adjustment");
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, STOP);
      break;

    case STOP:
    default:
      rotateMotor(FRONT_RIGHT_MOTOR, STOP);
      rotateMotor(BACK_RIGHT_MOTOR, STOP);
      rotateMotor(FRONT_LEFT_MOTOR, STOP);
      rotateMotor(BACK_LEFT_MOTOR, STOP);    
      break;
  }
}

void handleRoot(AsyncWebServerRequest *request) 
{
  request->send_P(200, "text/html", htmlHomePage);
}

void handleHandGesture(AsyncWebServerRequest *request) 
{
  if (request->hasParam("gesture", true)) {
    String gesture = request->getParam("gesture", true)->value();
    Serial.printf("Received hand gesture: %s\n", gesture.c_str());
    
    if (gesture == "left") {
      processCarMovement("11");  // HAND_LEFT_RAISED
    } else if (gesture == "right") {
      processCarMovement("12");  // HAND_RIGHT_RAISED
    } else if (gesture == "both") {
      processCarMovement("13");  // HAND_BOTH_RAISED
    } else if (gesture == "none") {
      processCarMovement("14");  // HAND_NONE_RAISED
    } else {
      processCarMovement("0");   // STOP
    }
    
    request->send(200, "text/plain", "OK");
  } else {
    request->send(400, "text/plain", "Missing gesture parameter");
  }
}

void handlePersonTracking(AsyncWebServerRequest *request) 
{
  if (request->hasParam("action", true)) {
    String action = request->getParam("action", true)->value();
    Serial.printf("Received tracking command: %s\n", action.c_str());
    
    if (action == "track_left") {
      processCarMovement("15");  // TRACK_LEFT
    } else if (action == "track_right") {
      processCarMovement("16");  // TRACK_RIGHT
    } else if (action == "track_center") {
      processCarMovement("17");  // TRACK_CENTER
    } else {
      processCarMovement("0");   // STOP
    }
    
    request->send(200, "text/plain", "OK");
  } else {
    request->send(400, "text/plain", "Missing action parameter");
  }
}

void handleNotFound(AsyncWebServerRequest *request) 
{
  request->send(404, "text/plain", "File Not Found");
}

void onWebSocketEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) 
{                      
  switch (type) 
  {
    case WS_EVT_CONNECT:
      Serial.printf("WebSocket client #%u connected from %s\n", client->id(), client->remoteIP().toString().c_str());
      break;
    case WS_EVT_DISCONNECT:
      Serial.printf("WebSocket client #%u disconnected\n", client->id());
      processCarMovement("0");
      break;
    case WS_EVT_DATA:
      AwsFrameInfo *info;
      info = (AwsFrameInfo*)arg;
      if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) 
      {
        std::string myData = "";
        myData.assign((char *)data, len);
        processCarMovement(myData.c_str());       
      }
      break;
    default:
      break;  
  }
}

void setUpPinModes()
{
  // Configure PWM for all motor pins
  for (int i = 0; i < motorPins.size(); i++)
  {
    // Configure PWM channels for each motor pin
    ledcSetup(i * 2, PWM_FREQUENCY, PWM_RESOLUTION);     // Channel for pinIN1
    ledcSetup(i * 2 + 1, PWM_FREQUENCY, PWM_RESOLUTION); // Channel for pinIN2
    
    // Attach pins to PWM channels
    ledcAttachPin(motorPins[i].pinIN1, i * 2);
    ledcAttachPin(motorPins[i].pinIN2, i * 2 + 1);
    
    // Initialize motors to stop
    rotateMotor(i, STOP);  
  }
}

void setup(void) 
{
  setUpPinModes();
  Serial.begin(115200);

  // Connect to WiFi network instead of creating access point
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  // Wait for connection
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.print("Connected to WiFi network: ");
  Serial.println(ssid);
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Signal strength (RSSI): ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");

  server.on("/", HTTP_GET, handleRoot);
  server.on("/hand-gesture", HTTP_POST, handleHandGesture);
  server.on("/person-tracking", HTTP_POST, handlePersonTracking);
  server.onNotFound(handleNotFound);

  ws.onEvent(onWebSocketEvent);
  server.addHandler(&ws);
  server.begin();
  Serial.println("HTTP server started");
  
  // Test motor directions on startup
  Serial.println("=== MOTOR DIRECTION CALIBRATION ===");
  Serial.println("Testing motor directions in 3 seconds...");
  delay(3000);
  testMotorDirections();
  
  Serial.println("Smart car is ready for commands!");
}

void loop() 
{
  ws.cleanupClients(); 
}

void testMotorDirections()
{
  Serial.println("=== MOTOR DIRECTION TEST ===");
  Serial.println("Testing each motor individually...");
  Serial.println("Watch each motor and verify it rotates FORWARD:");
  
  for (int i = 0; i < 4; i++)
  {
    String motorName;
    switch(i) {
      case FRONT_RIGHT_MOTOR: motorName = "FRONT_RIGHT_MOTOR"; break;
      case BACK_RIGHT_MOTOR: motorName = "BACK_RIGHT_MOTOR"; break;
      case FRONT_LEFT_MOTOR: motorName = "FRONT_LEFT_MOTOR"; break;
      case BACK_LEFT_MOTOR: motorName = "BACK_LEFT_MOTOR"; break;
    }
    
    Serial.printf("Testing %s (Motor %d)...\n", motorName.c_str(), i);
    Serial.println("Motor should rotate FORWARD for 2 seconds");
    
    // Run motor forward
    rotateMotor(i, FORWARD);
    delay(2000);
    
    // Stop motor
    rotateMotor(i, STOP);
    Serial.println("Motor stopped");
    
    delay(1000); // Pause between tests
  }
  
  Serial.println("=== TEST COMPLETE ===");
  Serial.println("If any motor rotated backwards, update motorDirectionCorrection array:");
  Serial.println("Set motorDirectionCorrection[motor_number] = -1 for backwards motors");
}