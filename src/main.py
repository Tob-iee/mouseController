'''
Program to implement the various pipelines necessary for the pointer movement direction
'''

import numpy as np
import cv2
import argparse
import logging
from input_feeder import InputFeeder
from gaze_estimation import Gaze
from mouse_controller import MouseController
from facial_landmarks_detection import FacialLandmarksDetection
from head_pose_estimation import HeadPoseEstimation
from face_detection import FaceDetection
import time
import os

logging.basicConfig(filename='mouseController.log', level=logging.DEBUG)


CPU_EXTENSION="/opt/intel/openvino/deployment_tools/inference_engine/lib/intel64/libcpu_extension_sse4.so"
performance_directory_path="../"
def get_args():
    '''
    Gets the arguments from the command line.
    '''
    parser = argparse.ArgumentParser()
    # -- Add required and optional groups
    required = parser.add_argument_group('required arguments')
    optional = parser.add_argument_group('optional arguments')

    # -- create the arguments
    
    optional.add_argument("-m_f", help="path to face detection model", default='../models/face-detection-adas-binary-0001', required=False)
    optional.add_argument("-m_l", help="path to facial landmarks detection model", default='../models/landmarks-regression-retail-0009', required=False)
    optional.add_argument("-m_h", help="path to head pose estimation detection model", default='../models/head-pose-estimation-adas-0001', required=False)
    optional.add_argument("-m_g", help="path to gaze detection model", default='../models/gaze-estimation-adas-0002',required=False)
    '''
    required.add_argument("-m_f", help="path to face detection model", required=True)
    required.add_argument("-m_l", help="path to facial landmarks detection model", required=True)
    required.add_argument("-m_h", help="path to head pose estimation detection model", required=True)
    required.add_argument("-m_g", help="path to gaze detection model", required=True)
    '''
    optional.add_argument("-l", help="MKLDNN (CPU)-targeted custom layers.", default=CPU_EXTENSION, required=False)
    optional.add_argument("-d", help="Specify the target device type", default='CPU')
    required.add_argument("-i", help="path to video/image file or 'cam' for webcam", required=True)
    optional.add_argument("-p", help="path to store performance stats", required=False)
    optional.add_argument("-vf", help="specify flags from m_f, m_l, m_h, m_g e.g. -vf m_f m_l m_h m_g (seperate each flag by space) for visualization of the output of intermediate models", nargs='+', default=[], required=False)
    args = parser.parse_args()

    return args

def writePerformanceStats(args,model_stats_txt,model_inference_time,model_fps,model_load_time):
    with open(os.path.join(performance_directory_path+args.p, model_stats_txt), 'w') as f:
                f.write(str(model_inference_time)+'\n')
                f.write(str(model_fps)+'\n')
                f.write(str(model_load_time)+'\n')

def pipelines(args):
    # enable logging for the function
    logger = logging.getLogger(__name__)
    
    # grab the parsed parameters
    faceDetectionModel=args.m_f
    landmarksDetectionModel=args.m_l
    headPoseEstimationModel=args.m_h
    gazeDetectionModel=args.m_g
    device=args.d
    customLayers=args.l
    inputFile=args.i
    visualization_flag = args.vf

    # initialize feed
    single_image_format = ['jpg','tif','png','jpeg', 'bmp']
    if inputFile.split(".")[-1].lower() in single_image_format:
        feed=InputFeeder('image',inputFile)
    elif args.i == 'cam':
        feed=InputFeeder('cam')
    else:
        feed = InputFeeder('video',inputFile)

    # load feed data
    feed.load_data()

    # initialize and load the models
    start_face_model_load_time = time.time()
    faceDetectionPipeline=FaceDetection(faceDetectionModel, device, customLayers)
    faceDetectionPipeline.load_model()
    face_model_load_time = time.time() - start_face_model_load_time

    start_landmark_model_load_time = time.time()
    landmarksDetectionPipeline=FacialLandmarksDetection(landmarksDetectionModel, device, customLayers)
    landmarksDetectionPipeline.load_model()
    landmark_model_load_time = time.time() - start_landmark_model_load_time
    
    start_headpose_model_load_time = time.time()
    headPoseEstimationPipeline=HeadPoseEstimation(headPoseEstimationModel, device, customLayers)
    headPoseEstimationPipeline.load_model()
    headpose_model_load_time = time.time() - start_headpose_model_load_time
    
    start_gaze_model_load_time = time.time()
    gazeDetectionPipeline=Gaze(gazeDetectionModel, device, customLayers)
    gazeDetectionPipeline.load_model('Gaze')
    gaze_model_load_time = time.time() - start_gaze_model_load_time
    
    
    # count the number of frames
    frameCount = 0

    # collate frames from the feeder and feed into the detection pipelines
    for _, frame in feed.next_batch():

        if not _:
            break
        frameCount+=1
        #if frameCount%5==0:
            #cv2.imshow('video', cv2.resize(frame,(500,500)))

        key = cv2.waitKey(60)
        start_face_inference_time = time.time()
        croppedFace = faceDetectionPipeline.predict(frame)
        face_inference_time = time.time() - start_face_inference_time

        if 'm_f' in visualization_flag:
            cv2.imshow('cropped face', croppedFace)

        if type(croppedFace)==int:
            logger.info("no face detected")
            if key==27:
                break
            continue
        
        start_landmark_inference_time = time.time()
        left_eye_image,right_eye_image, landmarkedFace = landmarksDetectionPipeline.predict(croppedFace.copy())
        landmark_inference_time = time.time() - start_landmark_inference_time    

        if left_eye_image.any() == None or right_eye_image.any() == None:
            logger.info("image probably too dark or eyes covered, hence could not detect landmarks")
            continue
        
        if 'm_l' in visualization_flag:
            cv2.imshow('Face output', landmarkedFace)

        start_headpose_inference_time = time.time()
        head_pose_angles, himage=headPoseEstimationPipeline.predict(croppedFace.copy())   
        headpose_inference_time = time.time() - start_headpose_inference_time

        if 'm_h' in visualization_flag:
            cv2.imshow('Head Pose Angles', himage)
        
        start_gaze_inference_time = time.time()
        x,y=gazeDetectionPipeline.predict(left_eye_image ,right_eye_image, head_pose_angles)
        gaze_inference_time = time.time() - start_gaze_inference_time

        if 'm_g' in visualization_flag:
            cv2.putText(landmarkedFace, "Estimated x:{:.2f} | Estimated y:{:.2f}".format(x,y), (10,20), cv2.FONT_HERSHEY_COMPLEX, 0.25, (0,255,0),1)
            cv2.imshow('Gaze Estimation', landmarkedFace)

        mouseVector=MouseController('medium','fast')


        if frameCount%5==0:
            mouseVector.move(x,y)

        if key==27:
            break
        
        if args.p != None and face_inference_time != 0 and landmark_inference_time != 0 and headpose_inference_time != 0 and gaze_inference_time != 0:
            output_path = performance_directory_path+args.p
            if not os.path.exists(output_path):
                os.makedirs(output_path)

            fps_face = 1/face_inference_time
            fps_landmark = 1/landmark_inference_time
            fps_headpose = 1/headpose_inference_time
            fps_gaze = 1/gaze_inference_time

            writePerformanceStats(args,'face_stats.txt',face_inference_time,fps_face,face_model_load_time)
            writePerformanceStats(args,'landmark_stats.txt',landmark_inference_time,fps_landmark,landmark_model_load_time)
            writePerformanceStats(args,'headpose_stats.txt',headpose_inference_time,fps_headpose,headpose_model_load_time)
            writePerformanceStats(args,'gaze_stats.txt',gaze_inference_time,fps_gaze,gaze_model_load_time)
        
        
    logger.info("The End")
    cv2.destroyAllWindows()
    feed.close()

def main():
    args=get_args()
    pipelines(args) 

if __name__ == '__main__':
    main()