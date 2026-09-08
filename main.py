<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>3D HTML5 FPS Game</title>
    <style>
        body {
            margin: 0;
            overflow: hidden;
            font-family: Arial, sans-serif;
            user-select: none;
        }
        #crosshair {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 10px;
            height: 10px;
            color: white;
            font-size: 24px;
            transform: translate(-50%, -50%);
            pointer-events: none;
            z-index: 10;
        }
        #ui {
            position: absolute;
            top: 20px;
            left: 20px;
            color: white;
            font-size: 20px;
            font-weight: bold;
            text-shadow: 2px 2px 4px #000000;
            z-index: 10;
        }
        #instructions {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            color: white;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-size: 24px;
            cursor: pointer;
            z-index: 20;
        }
    </style>
    <!-- Three.js 3D 엔진 불러오기 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>

    <div id="crosshair">+</div>
    <div id="ui">
        플레이어 HP: <span id="playerHp">100</span><br>
        적 HP: <span id="enemyHp">100</span>
    </div>
    <div id="instructions">
        <h1>클릭하여 게임 시작</h1>
        <p>이동: W, A, S, D</p>
        <p>시점: 마우스 이동</p>
        <p>사격: 마우스 좌클릭</p>
    </div>

    <script>
        // --- 1. 기본 씬 설정 ---
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x87ceeb); // 하늘색 배경
        scene.fog = new THREE.Fog(0x87ceeb, 0, 75);

        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        document.body.appendChild(renderer.domElement);

        // 조명 추가
        const light = new THREE.HemisphereLight(0xffffff, 0x444444, 1);
        light.position.set(0, 20, 0);
        scene.add(light);

        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(10, 20, 10);
        scene.add(dirLight);

        // 바닥 및 장애물(벽) 생성
        const floorGeo = new THREE.PlaneGeometry(100, 100);
        const floorMat = new THREE.MeshLambertMaterial({ color: 0x2e8b57 });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        scene.add(floor);

        // 마임크래프트 느낌의 상자 장애물들
        for(let i = 0; i < 15; i++) {
            const boxGeo = new THREE.BoxGeometry(4, 4, 4);
            const boxMat = new THREE.MeshLambertMaterial({ color: 0x8b4513 });
            const box = new THREE.Mesh(boxGeo, boxMat);
            box.position.set((Math.random() - 0.5) * 60, 2, (Math.random() - 0.5) * 60);
            scene.add(box);
        }

        // --- 2. 플레이어 설정 ---
        const player = {
            hp: 100,
            speed: 0.15,
            position: camera.position
        };
        player.position.set(0, 1.6, 10); // 눈높이 위치

        // --- 3. 적 AI 설정 ---
        const enemyGeo = new THREE.SphereGeometry(1, 16, 16);
        const enemyMat = new THREE.MeshLambertMaterial({ color: 0xff0000 });
        const enemy = new THREE.Mesh(enemyGeo, enemyMat);
        enemy.position.set(0, 1, -20);
        scene.add(enemy);

        let enemyHp = 100;
        let enemyLastShot = 0;

        // --- 4. 총알 관리 배열 ---
        const bullets = [];
        const enemyBullets = [];

        // --- 5. 컨트롤 및 입력 처리 ---
        const keys = {};
        let isLocked = false;

        const instructions = document.getElementById('instructions');

        instructions.addEventListener('click', () => {
            document.body.requestPointerLock();
        });

        document.addEventListener('pointerlockchange', () => {
            if (document.pointerLockElement === document.body) {
                isLocked = true;
                instructions.style.display = 'none';
            } else {
                isLocked = false;
                instructions.style.display = 'flex';
            }
        });

        // 회전 각도 관리
        let yaw = 0;
        let pitch = 0;

        document.addEventListener('mousemove', (e) => {
            if (!isLocked) return;
            
            yaw -= e.movementX * 0.002;
            pitch -= e.movementY * 0.002;

            // 위아래 시점 제한 (목이 넘어가지 않도록)
            pitch = Math.max(-Math.PI / 2 + 0.1, Math.min(Math.PI / 2 - 0.1, pitch));

            const euler = new THREE.Euler(0, 0, 0, 'YXZ');
            euler.x = pitch;
            euler.y = yaw;
            camera.quaternion.setFromEuler(euler);
        });

        document.addEventListener('keydown', (e) => keys[e.code] = true);
        document.addEventListener('keyup', (e) => keys[e.code] = false);

        // 발사 처리 (좌클릭)
        document.addEventListener('mousedown', (e) => {
            if (!isLocked || e.button !== 0 || player.hp <= 0) return;

            // 플레이어 총알 생성
            const bulletGeo = new THREE.SphereGeometry(0.1, 8, 8);
            const bulletMat = new THREE.MeshBasicMaterial({ color: 0xffff00 });
            const bullet = new THREE.Mesh(bulletGeo, bulletMat);

            bullet.position.copy(camera.position);
            
            // 카메라가 바라보는 방향 계산
            const dir = new THREE.Vector3();
            camera.getWorldDirection(dir);
            bullet.userData = { velocity: dir.multiplyScalar(0.8) };

            scene.add(bullet);
            bullets.push(bullet);
        });

        // --- 6. 게임 루프 (업데이트) ---
        function animate() {
            requestAnimationFrame(animate);

            if (isLocked && player.hp > 0 && enemyHp > 0) {
                // [플레이어 이동 처리]
                const moveVector = new THREE.Vector3();
                if (keys['KeyW']) moveVector.z -= 1;
                if (keys['KeyS']) moveVector.z += 1;
                if (keys['KeyA']) moveVector.x -= 1;
                if (keys['KeyD']) moveVector.x += 1;

                moveVector.normalize();
                moveVector.applyAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
                camera.position.addScaledVector(moveVector, player.speed);
                camera.position.y = 1.6; // 높이 고정

                // [적 AI 행동]
                const dirToPlayer = new THREE.Vector3().subVectors(player.position, enemy.position);
                const distance = dirToPlayer.length();

                // 플레이어 쪽으로 추적
                if (distance > 5) {
                    dirToPlayer.y = 0;
                    dirToPlayer.normalize();
                    enemy.position.addScaledVector(dirToPlayer, 0.03);
                }

                // 일정 주기마다 플레이어에게 총알 발사
                const now = Date.now();
                if (now - enemyLastShot > 1500) { 
                    enemyLastShot = now;
                    const eBulletGeo = new THREE.SphereGeometry(0.15, 8, 8);
                    const eBulletMat = new THREE.MeshBasicMaterial({ color: 0xff0055 });
                    const eBullet = new THREE.Mesh(eBulletGeo, eBulletMat);
                    
                    eBullet.position.copy(enemy.position);
                    const shootDir = new THREE.Vector3().subVectors(player.position, enemy.position).normalize();
                    eBullet.userData = { velocity: shootDir.multiplyScalar(0.4) };

                    scene.add(eBullet);
                    enemyBullets.push(eBullet);
                }

                // [플레이어 총알 이동 & 충돌 판정]
                for (let i = bullets.length - 1; i >= 0; i--) {
                    const b = bullets[i];
                    b.position.add(b.userData.velocity);

                    // 적과 총알 충돌 확인
                    if (b.position.distanceTo(enemy.position) < 1.2) {
                        enemyHp -= 20;
                        document.getElementById('enemyHp').innerText = Math.max(0, enemyHp);
                        scene.remove(b);
                        bullets.splice(i, 1);

                        if (enemyHp <= 0) {
                            scene.remove(enemy);
                            alert("승리했습니다! 적을 처치했습니다.");
                            location.reload();
                        }
                        continue;
                    }

                    // 일정 거리 이상 넘어가면 사거리 제한으로 삭제
                    if (b.position.length() > 100) {
                        scene.remove(b);
                        bullets.splice(i, 1);
                    }
                }

                // [적 총알 이동 & 충돌 판정]
                for (let i = enemyBullets.length - 1; i >= 0; i--) {
                    const eb = enemyBullets[i];
                    eb.position.add(eb.userData.velocity);

                    // 플레이어와 충돌 확인
                    if (eb.position.distanceTo(player.position) < 0.8) {
                        player.hp -= 10;
                        document.getElementById('playerHp').innerText = Math.max(0, player.hp);
                        scene.remove(eb);
                        enemyBullets.splice(i, 1);

                        if (player.hp <= 0) {
                            alert("패배했습니다! 적의 공격에 쓰러졌습니다.");
                            location.reload();
                        }
                        continue;
                    }

                    if (eb.position.length() > 100) {
                        scene.remove(eb);
                        enemyBullets.splice(i, 1);
                    }
                }
            }

            renderer.render(scene, camera);
        }

        // 창 크기 조절 대응
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });

        animate();
    </script>
</body>
</html>
