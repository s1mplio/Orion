import cv2


class CameraService:
    """
    Responsible only for interacting with the webcam.

    Responsibilities:
    - Open camera
    - Read frames
    - Release camera
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.camera = None

    def start(self):
        """Initialize webcam."""

        self.camera = cv2.VideoCapture(self.camera_index)

        if not self.camera.isOpened():
            raise RuntimeError("Unable to open webcam.")

        print("Camera started.")

    def get_frame(self):
        """
        Returns:
            frame (numpy.ndarray)
        """

        if self.camera is None:
            raise RuntimeError("Camera not started.")

        success, frame = self.camera.read()

        if not success:
            raise RuntimeError("Unable to capture frame.")

        return frame

    def stop(self):
        """Release webcam."""

        if self.camera is not None:
            self.camera.release()

        cv2.destroyAllWindows()

        print("Camera stopped.")


if __name__ == "__main__":

    camera = CameraService()

    camera.start()

    try:

        while True:

            frame = camera.get_frame()

            cv2.imshow("Orion Vision", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:

        camera.stop()