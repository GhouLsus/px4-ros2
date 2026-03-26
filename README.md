# ROS 2 + PX4 SITL Mini Project

## About

A end-to-end aerial robotics pipeline built on Ubuntu 22.04 dual-boot setup. The system runs a simulated multicopter in PX4 SITL, bridges vehicle state into ROS 2 via uXRCE-DDS, pulls a simulated camera feed from Gazebo into a ROS 2 perception node, and records everything into a rosbag2.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Gazebo Harmonic                      │
│                                                         │
│                                                         │
│   ┌─────────────┐          ┌──────────────────────┐     │
│   │    drone    │          │  Camera Sensor       │     │
│   │             │          │                      │     │ 
│   │             │          └──────────┬───────────┘     │
│   └──────┬──────┘                     │                 │
└──────────┼──────────────────────────  │  ───────────────┘
           │                            │ gz.msgs.Image
           ▼                            ▼
┌─────────────────────┐     ┌───────────────────────────┐
│   PX4 SITL          │     │   ros_gz_bridge           │
│   (uXRCE-DDS client)│     │   (Gazebo → ROS 2 bridge) │
└─────────┬───────────┘     └───────────────┬───────────┘
          │ UDP :8888                       │
          ▼                                 ▼
┌─────────────────────┐     ┌───────────────────────────┐
│  MicroXRCEAgent     │     │   camera_node.py          │
│                     │     │   - subscribes to camera  │
└─────────┬───────────┘     │   - runs bright target    │
          │                 │     detection via OpenCV  │
          ▼                 │   - publishes /camera/    │
┌─────────────────────┐     │                           │
│   ROS 2 (Humble)    │     └───────────────────────────┘
│                     │
│                     │     ┌───────────────────────────┐
│                     │     │       rosbag2             │
│                     │────▶│  records all topics       │
│                     │     │  for post-analysis        │
│                     │     └───────────────────────────┘
└─────────────────────┘
```

---

## System Requirements

- Ubuntu 22.04
- NVIDIA GPU with driver 580+ recommended
- 16GB RAM minimum (Gazebo + PX4 + ROS 2 is heavy)
- ~20GB free disk space

---

## Installation

### 1. Ubuntu 22.04

Fresh dual-boot or VM install. Make sure secure boot and BitLocker are disabled before partitioning, learned this the hard way.

### 2. NVIDIA Drivers

```bash
ubuntu-drivers devices          # check what's recommended
sudo ubuntu-drivers autoinstall
sudo reboot
nvidia-smi                      # verify after reboot
```

### 3. ROS 2 Humble

Follow the official guide: https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html

Verify with the talker/listener demo before moving on.

### 4. PX4 Autopilot

```bash
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
bash ./Tools/setup/ubuntu.sh
sudo reboot
```

The `--recursive` flag is important — skipping it means missing submodules. The clone takes hours to build. The `ubuntu.sh` script installs Gazebo Harmonic automatically, so don't install Gazebo separately.

### 5. MicroXRCE-DDS Agent

This is the bridge agent that runs on the Ubuntu side and connects to PX4's built-in DDS client.

```bash
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build && cd build
cmake ..
make -j$(nproc)
sudo cmake --install .
sudo ldconfig                   # important — fixes shared library not found error
MicroXRCEAgent --help           # verify install
```

### 6. QGroundControl

Download the AppImage from https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html

```bash
chmod +x QGroundControl-x86_64.AppImage                #after installation just run this command, dont waste time over the other commands therer.
./QGroundControl-x86_64.AppImage
```

### 7. Gazebo ROS Bridge

```bash
sudo apt install ros-humble-ros-gzharmonic -y
```

### 8. px4_msgs Workspace

```bash
mkdir -p ~/ws_px4/src
cd ~/ws_px4/src
git clone https://github.com/PX4/px4_msgs.git
cd ~/ws_px4
source /opt/ros/humble/setup.bash
colcon build
```


### 9. cv_bridge + OpenCV

```bash
sudo apt install ros-humble-cv-bridge python3-opencv -y
pip3 install "numpy<2"          # This is very important, we need to use this version.
```

---

## Running the Stack

Open 5 terminals. Run in this exact order.

**Terminal 1 — PX4 SITL + Gazebo:**
```bash
cd ~/PX4-Autopilot
make px4_sitl gz_x500_mono_cam
```
Wait for Gazebo to open and the `pxh>` prompt to appear.

**Terminal 2 — uXRCE-DDS Agent:**
```bash
MicroXRCEAgent udp4 -p 8888
```

**Terminal 3 — Camera Bridge:**
```bash
source /opt/ros/humble/setup.bash
ros2 run ros_gz_bridge parameter_bridge \
  /world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image@sensor_msgs/msg/Image@gz.msgs.Image
```

**Terminal 4 — QGroundControl:**
```bash
cd ~/Downloads
./QGroundControl-x86_64.AppImage
```
QGC must be running before takeoff — PX4 will deny arming without a GCS connection.

**Terminal 5 — Perception Node:**
```bash
source /opt/ros/humble/setup.bash
source ~/ws_px4/install/setup.bash
ros2 run camera_perception camera_node
```

**Takeoff (in Terminal 1 pxh> shell):**
```bash
commander takeoff
```

---

## Verifying the Pipeline

Check ROS 2 topics are flowing:
```bash
source /opt/ros/humble/setup.bash
source ~/ws_px4/install/setup.bash
ros2 topic list | grep -E "camera|fmu"
```

Check camera frame rate:
```bash
ros2 topic hz /world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image
# expect ~15-17 Hz
```

Check live vehicle position:
```bash
ros2 topic echo /fmu/out/vehicle_local_position_v1
```

Processed frames are saved to `/tmp/latest_frame.jpg` and also published on `/camera/processed`.

---

## Recording a Rosbag

```bash
source /opt/ros/humble/setup.bash
source ~/ws_px4/install/setup.bash
ros2 bag record -o ~/flight_bag \
  /fmu/out/vehicle_local_position_v1 \
  /fmu/out/vehicle_status_v3 \
  /fmu/out/vehicle_attitude \
  /world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image \
  /camera/processed
```

Let it record during flight, then `Ctrl+C`. Inspect with:

```bash
ros2 bag info ~/flight_bag
```

---

## Rosbag Observations

From a 53-second flight recording:

| Topic | Messages | Rate | Notes |
|---|---|---|---|
| `/fmu/out/vehicle_attitude` | 1365 | ~25 Hz | Consistent IMU rate |
| `/fmu/out/vehicle_local_position_v1` | 1364 | ~25 Hz | EKF running healthy |
| `/world/.../camera/image` | 829 | ~15 Hz | Raw camera stream |
| `/camera/processed` | 623 | ~12 Hz | After perception processing |
| `/fmu/out/vehicle_status_v3` | 56 | ~1 Hz | Arming and mode changes |

Total bag size: 5.0 GiB — majority from raw image stream.

---

## Perception Node

Located at `src/camera_perception/camera_perception/camera_node.py`.

The node subscribes to the Gazebo camera topic, converts each frame using `cv_bridge`, runs a simple bright-target detector using OpenCV thresholding and contour detection, draws bounding boxes around detected regions (area > 500px), logs detections with position and area, saves the latest frame to `/tmp/latest_frame.jpg`, and publishes the processed frame on `/camera/processed`.

This is intentionally simple — the goal was a working end-to-end pipeline, not a production detector.

---

## Issues Faced

**BitLocker blocking dual boot** — Had to disable BitLocker from Windows before repartitioning. Took most of a day to figure out.

**MicroXRCEAgent shared library error** — After install, running `MicroXRCEAgent` gave `libmicroxrcedds_agent.so.2.4: cannot open shared object file`. Fixed with `sudo ldconfig`.

**commander takeoff arming denied** — PX4 refused to arm with `Resolve system health failures first`. The fix was simply opening QGroundControl — PX4 requires a GCS connection before it will arm in SITL.

**NumPy version conflict** — `cv_bridge` was compiled against NumPy 1.x but the system had 2.2.6 installed. Fixed by downgrading: `pip3 install "numpy<2"`.

**Wrong camera topic** — Initially bridged `/camera` which had no data. Used `gz topic -l | grep camera` to find the actual Gazebo topic path and updated the bridge command.

---

## Why uXRCE-DDS over MAVROS

The assignment recommended uXRCE-DDS as the preferred baseline and it is PX4's official ROS 2 integration path. I have prior experience with MAVLink from a drone internship (Raphe mPhibr) but chose to use the recommended stack since it's what production PX4 + ROS 2 systems use going forward. MAVROS is being phased out in favour of this approach.

---

## Dependencies Summary

| Tool | Version |
|---|---|
| Ubuntu | 22.04 LTS |
| ROS 2 | Humble |
| PX4 Autopilot | main (Mar 2026) |
| Gazebo | Harmonic 8.11.0 |
| MicroXRCE-DDS Agent | 2.4.x |
| px4_msgs | main |
| OpenCV | 4.x (python3-opencv) |
| cv_bridge | ros-humble-cv-bridge |
| NumPy | 1.26.4 (downgraded) |

---

## Limitations

- Bright target detector produces false positives on uniform sky — works better when drone is flying over a textured surface
- Rosbag is 5GB for a 53-second flight due to uncompressed image storage — in production would use compressed image topics
- No launch file yet — startup requires 5 manually ordered terminals

---

## Improvements

- Write a single ROS 2 launch file to bring up the whole stack in one command
- Replace the threshold detector with a proper ArUco marker or landing pad detector
- Add compressed image transport to reduce rosbag size
- Integrate a state machine so the drone can autonomously search and descend toward a detected target

---

Took help from Claude AI and chatGPT for the setup, documentation and fine tuning things, used official guides for tutorials and initial understanding.