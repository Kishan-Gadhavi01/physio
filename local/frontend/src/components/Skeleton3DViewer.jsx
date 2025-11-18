import React, { useRef, useEffect, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Line, Sphere } from '@react-three/drei';
import { SKELETON_SEGMENTS } from '../utils/kinematics'; // Assuming this is your file path

/**
 * Renders the individual joints and bones of the skeleton.
 * It also centers the skeleton at the origin based on the pelvis position.
 */
function Skeleton({ keypoints }) {
    if (!keypoints || keypoints.length === 0) return null;
    
    const groupRef = useRef();

    // This effect centers the entire skeleton group so the pelvis (keypoint 0)
    // is at the world origin [0, 0, 0].
    useEffect(() => {
        if (groupRef.current) {
            const pelvisPosition = keypoints[0];
            if (pelvisPosition) {
                groupRef.current.position.set(-pelvisPosition[0], -pelvisPosition[1], -pelvisPosition[2]);
            }
        }
    }, [keypoints]);

    return (
        <group ref={groupRef}>
            {/* Render a sphere for each keypoint (joint) */}
            {keypoints.map((point, index) => (
                <Sphere key={index} position={point} args={[0.02]}>
                    <meshStandardMaterial color="indianred" />
                </Sphere>
            ))}
            {/* Render a line for each bone segment */}
            {Object.values(SKELETON_SEGMENTS).map((segment, i) => (
                <React.Fragment key={i}>
                    {segment.links.map(([startIdx, endIdx], j) => {
                        // Ensure the keypoints exist before trying to render a line
                        if (startIdx < keypoints.length && endIdx < keypoints.length) {
                            const startPoint = keypoints[startIdx];
                            const endPoint = keypoints[endIdx];
                            return <Line key={j} points={[startPoint, endPoint]} color={segment.color} lineWidth={3} />;
                        }
                        return null;
                    })}
                </React.Fragment>
            ))}
        </group>
    );
}

/**
 * Sets up the 3D scene and transforms the incoming keypoint data
 * for correct orientation before passing it to the Skeleton component.
 */
function Skeleton3DViewer({ keypoints }) {
  if (!keypoints || keypoints.length === 0) {
    return <div className="placeholder" style={{width: '100%', height: '100%', display: 'grid', placeContent: 'center'}}>3D View</div>;
  }

  // Memoize the transformation of keypoints to prevent recalculation on every render.
  // This is the CRITICAL FIX for the orientation problem.
  const transformedKeypoints = useMemo(() => {
    // Maps [x, y, z] from a Y-down system to [x, -y, -z] for Three.js's Y-up system.
    return keypoints.map(point => [point[0], point[2], point[1]]);
  }, [keypoints]);

  return (
    <Canvas camera={{ position: [0, 1, 2.5], fov: 50 }}>
      <ambientLight intensity={0.8} />
      <directionalLight position={[10, 10, 5]} intensity={1.2} />
      
      {/* Pass the CORRECTED keypoints to the Skeleton component */}
      <Skeleton keypoints={transformedKeypoints} />
      
      <OrbitControls />
      <gridHelper args={[10, 10, '#4A5568', '#2D3748']} />
    </Canvas>
  );
}

export default Skeleton3DViewer;