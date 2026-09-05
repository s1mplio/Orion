import base64
import cv2

from openai import OpenAI


class VisionService:
    """
    Responsible for sending camera frames to a vision-capable LLM.

    Flow:

        Camera frame
             ↓
        JPEG encoding
             ↓
        Base64
             ↓
        OmniRoute
             ↓
        Vision model
             ↓
        Text description
    """

    def __init__(self):

        self.client = OpenAI(
            base_url="http://localhost:20128/v1",
            api_key="omniroute"
        )

        self.model = "auto"

        print("Vision Service connected to OmniRoute.")

    def analyze_frame(self, frame, prompt: str = None) -> str:
        """
        Analyze a single OpenCV camera frame.

        Args:
            frame:
                OpenCV image as a numpy array.

            prompt:
                Question/instruction for the vision model.

        Returns:
            Text response from the vision model.
        """

        if frame is None:
            raise ValueError("Frame cannot be None.")

        if prompt is None:
            prompt = (
                "Describe what you can see in this image. "
                "Focus on important objects, people, text, "
                "and the overall scene. "
                "Do not invent details that are not visible."
            )

        # OpenCV uses BGR format.
        # Convert the frame to JPEG.
        success, encoded_image = cv2.imencode(
            ".jpg",
            frame
        )

        if not success:
            raise RuntimeError("Failed to encode camera frame.")

        # Convert JPEG bytes to Base64.
        image_base64 = base64.b64encode(
            encoded_image.tobytes()
        ).decode("utf-8")

        # Send image + text to the vision model.
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Orion, a visual AI companion. "
                        "Describe only what is actually visible. "
                        "If you are uncertain, say so."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:image/jpeg;base64,"
                                    f"{image_base64}"
                                )
                            }
                        }
                    ]
                }
            ],
            temperature=0
        )

        return response.choices[0].message.content.strip()


if __name__ == "__main__":

    print("Starting Orion Vision test...")

    from camera_services import CameraService

    camera = CameraService()
    vision = VisionService()

    camera.start()

    try:

        print("\nCamera started.")
        print("Press SPACE to analyze a frame.")
        print("Press Q to quit.\n")

        while True:

            frame = camera.get_frame()

            cv2.imshow(
                "Orion Vision Test",
                frame
            )

            key = cv2.waitKey(1) & 0xFF

            # Analyze current frame.
            if key == ord(" "):

                print("\nAnalyzing frame...")

                answer = vision.analyze_frame(
                    frame,
                    "What am I looking at? "
                    "Describe the important objects and scene."
                )

                print("\nOrion:")
                print(answer)

            # Quit.
            elif key == ord("q"):
                break

    finally:

        camera.stop()