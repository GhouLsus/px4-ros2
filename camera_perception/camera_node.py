import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.bridge = CvBridge()
        self.subscription = self.create_subscription(
            Image,
            '/world/default/model/x500_mono_cam_0/link/camera_link/sensor/camera/image',
            self.image_callback,
            10)
        self.publisher = self.create_publisher(Image, '/camera/processed', 10)
        self.get_logger().info('Camera node started, waiting for frames...')

    def image_callback(self, msg):
        # Convert ROS image to OpenCV
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        # Simple perception — detect bright regions (landing pad / target)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 500:
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                self.get_logger().info(f'Bright target detected at ({x},{y}), area={area:.0f}')
        
        # Save a frame as evidence
        cv2.imwrite('/tmp/latest_frame.jpg', frame)
        
        # Publish processed image
        processed_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.publisher.publish(processed_msg)

def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()