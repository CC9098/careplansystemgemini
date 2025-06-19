from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user, login_user, logout_user
from datetime import datetime, timedelta
import secrets
import json
import requests
import os
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from models import db, User, Resident, CarePlanHistory, CareTask, ShareableLink

api_v1 = Blueprint('api_v1', __name__)

def api_response(success, data=None, error=None, status_code=200):
    """標準化的 API 回應格式"""
    response = {
        "success": success,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if success:
        response["data"] = data
    else:
        response["error"] = error
    
    return jsonify(response), status_code

def call_deepseek_api(messages, max_tokens=2000):
    """調用 DeepSeek API"""
    deepseek_config = current_app.config.get('DEEPSEEK_CLIENT')
    if not deepseek_config:
        raise Exception("DeepSeek API not configured")
    
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(
            deepseek_config['base_url'],
            headers=deepseek_config['headers'],
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        current_app.logger.error(f"DeepSeek API error: {str(e)}")
        raise Exception(f"AI service error: {str(e)}")

# --- Authentication API ---

@api_v1.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    name = data.get('name', '')

    if not email or not password:
        return api_response(False, error={"message": "Email and password are required"}, status_code=400)

    if User.query.filter_by(email=email).first():
        return api_response(False, error={"message": "Email already registered"}, status_code=400)

    try:
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return api_response(True, data=user.to_dict(), status_code=201)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration error: {str(e)}")
        return api_response(False, error={"message": "Registration failed"}, status_code=500)

@api_v1.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return api_response(False, error={"message": "Email and password are required"}, status_code=400)

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(password):
        login_user(user)
        return api_response(True, data=user.to_dict())
    
    return api_response(False, error={"message": "Invalid credentials"}, status_code=401)

@api_v1.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return api_response(True, data={"message": "Successfully logged out"})

@api_v1.route('/auth/me', methods=['GET'])
@login_required
def get_current_user():
    return api_response(True, data=current_user.to_dict())

@api_v1.route('/auth/google', methods=['POST'])
def google_auth():
    """處理 Google ID Token 驗證"""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return api_response(False, error={"message": "Google ID token is required"}, status_code=400)
    
    try:
        # 驗證 Google ID Token
        google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        if not google_client_id:
            return api_response(False, error={"message": "Google OAuth not configured"}, status_code=500)
        
        # 驗證 token
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            google_client_id
        )
        
        # 獲取用戶信息
        email = idinfo['email']
        name = idinfo.get('name', '')
        google_id = idinfo['sub']
        
        # 查找或創建用戶
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # 創建新用戶
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                is_google_user=True
            )
            db.session.add(user)
            db.session.commit()
        else:
            # 更新現有用戶的 Google ID
            if not user.google_id:
                user.google_id = google_id
                user.is_google_user = True
                db.session.commit()
        
        # 登入用戶
        login_user(user)
        
        return api_response(True, data={
            "user": user.to_dict(),
            "message": "Successfully authenticated with Google"
        })
        
    except ValueError as e:
        # Token 無效
        current_app.logger.error(f"Google token validation error: {str(e)}")
        return api_response(False, error={"message": "Invalid Google token"}, status_code=401)
    except Exception as e:
        current_app.logger.error(f"Google auth error: {str(e)}")
        return api_response(False, error={"message": "Google authentication failed"}, status_code=500)

@api_v1.route('/auth/google-dev', methods=['POST'])
def google_auth_dev():
    """開發者模式 Google 認證"""
    current_app.logger.info(f"Flask ENV: {current_app.config.get('FLASK_ENV')}")
    
    if not current_app.config.get('FLASK_ENV') == 'development':
        return api_response(False, error={"message": "Development mode only"}, status_code=403)
    
    data = request.get_json()
    email = data.get('email', 'dev@example.com')
    name = data.get('name', 'Developer User')
    
    current_app.logger.info(f"Attempting dev auth for: {email}")
    
    try:
        # 查找或創建開發者用戶
        user = User.query.filter_by(email=email).first()
        if not user:
            current_app.logger.info("Creating new dev user")
            user = User(
                email=email,
                name=name,
                google_id='dev-' + email,
                is_google_user=True
            )
            db.session.add(user)
            db.session.commit()
            current_app.logger.info(f"Created user: {user.id}")
        else:
            current_app.logger.info(f"Found existing user: {user.id}")
        
        login_user(user)
        current_app.logger.info("Login successful")
        
        return api_response(True, data={
            "user": user.to_dict(),
            "message": "Development mode login successful"
        })
    except Exception as e:
        current_app.logger.error(f"Dev auth error: {str(e)}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return api_response(False, error={"message": f"Development authentication failed: {str(e)}"}, status_code=500)

# --- Residents CRUD API ---

@api_v1.route('/residents', methods=['GET'])
@login_required
def get_residents():
    try:
        residents = Resident.query.filter_by(owner_id=current_user.id).all()
        return api_response(True, data=[resident.to_dict() for resident in residents])
    except Exception as e:
        current_app.logger.error(f"Get residents error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch residents"}, status_code=500)

@api_v1.route('/residents', methods=['POST'])
@login_required
def create_resident():
    data = request.get_json()
    name = data.get('name')
    
    if not name:
        return api_response(False, error={"message": "Resident name is required"}, status_code=400)
    
    try:
        resident = Resident(
            name=name,
            age=data.get('age'),
            gender=data.get('gender'),
            room_number=data.get('room_number'),
            admission_date=datetime.strptime(data.get('admission_date'), '%Y-%m-%d').date() if data.get('admission_date') else None,
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            medical_conditions=data.get('medical_conditions'),
            medications=data.get('medications'),
            care_notes=data.get('care_notes'),
            owner_id=current_user.id
        )
        
        db.session.add(resident)
        db.session.commit()
        return api_response(True, data=resident.to_dict(), status_code=201)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create resident error: {str(e)}")
        return api_response(False, error={"message": "Failed to create resident"}, status_code=500)

@api_v1.route('/residents/<int:resident_id>', methods=['GET'])
@login_required
def get_resident(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        return api_response(True, data=resident.to_dict(include_tasks=True, include_history=True))
    except Exception as e:
        current_app.logger.error(f"Get resident error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch resident"}, status_code=500)

@api_v1.route('/residents/<int:resident_id>', methods=['PUT'])
@login_required
def update_resident(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        data = request.get_json()
        
        # 更新允許的字段
        for field in ['name', 'age', 'gender', 'room_number', 'emergency_contact_name', 
                     'emergency_contact_phone', 'medical_conditions', 'medications', 'care_notes']:
            if field in data:
                setattr(resident, field, data[field])
        
        if 'admission_date' in data and data['admission_date']:
            resident.admission_date = datetime.strptime(data['admission_date'], '%Y-%m-%d').date()
        
        resident.updated_at = datetime.utcnow()
        db.session.commit()
        
        return api_response(True, data=resident.to_dict())
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update resident error: {str(e)}")
        return api_response(False, error={"message": "Failed to update resident"}, status_code=500)

@api_v1.route('/residents/<int:resident_id>', methods=['DELETE'])
@login_required
def delete_resident(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        db.session.delete(resident)
        db.session.commit()
        
        return api_response(True, data={"message": "Resident deleted successfully"})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete resident error: {str(e)}")
        return api_response(False, error={"message": "Failed to delete resident"}, status_code=500)

# --- AI Analysis & Care Plans API ---

@api_v1.route('/analyze', methods=['POST'])
@login_required
def analyze():
    if current_user.get_remaining_usage() <= 0:
        return api_response(False, error={"message": "Usage limit exceeded. Please upgrade to premium."}, status_code=403)
    
    try:
        data = request.get_json()
        daily_log = data.get('daily_log', '')
        current_plan = data.get('current_plan', '')
        resident_info = data.get('resident_info', {})
        
        if not daily_log:
            return api_response(False, error={"message": "Daily log is required"}, status_code=400)
        
        # 構建 AI 分析提示
        messages = [
            {
                "role": "system",
                "content": "你是一位資深的照護專家，專門分析住民的日常記錄並提供專業的照護建議。請以專業、關懷的語調回應，並使用繁體中文。"
            },
            {
                "role": "user",
                "content": f"""
請分析以下住民的日常記錄，並提供專業的照護建議：

住民資訊：
姓名：{resident_info.get('name', '未提供')}
年齡：{resident_info.get('age', '未提供')}
醫療狀況：{resident_info.get('medical_conditions', '未提供')}
當前用藥：{resident_info.get('medications', '未提供')}

今日記錄：
{daily_log}

當前照護計畫：
{current_plan if current_plan else '無'}

請提供：
1. 對今日記錄的專業分析
2. 需要注意的健康狀況或風險
3. 具體的照護建議
4. 建議的後續行動計畫
"""
            }
        ]
        
        ai_analysis = call_deepseek_api(messages)
        current_user.increment_usage()
        
        return api_response(True, data={
            "analysis": ai_analysis,
            "remaining_usage": current_user.get_remaining_usage()
        })
        
    except Exception as e:
        current_app.logger.error(f"AI analysis error: {str(e)}")
        return api_response(False, error={"message": f"Analysis failed: {str(e)}"}, status_code=500)

@api_v1.route('/generate-care-plan', methods=['POST'])
@login_required
def generate_care_plan():
    if current_user.get_remaining_usage() <= 0:
        return api_response(False, error={"message": "Usage limit exceeded. Please upgrade to premium."}, status_code=403)
    
    try:
        data = request.get_json()
        resident_id = data.get('resident_id')
        analysis_result = data.get('analysis_result', '')
        additional_notes = data.get('additional_notes', '')
        
        if not resident_id:
            return api_response(False, error={"message": "Resident ID is required"}, status_code=400)
        
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        # 構建照護計畫生成提示
        messages = [
            {
                "role": "system",
                "content": "你是一位資深的照護計畫專家，擅長為安老院住民制定詳細、實用的照護計畫。請以專業格式回應，使用繁體中文。"
            },
            {
                "role": "user",
                "content": f"""
基於以下資訊，請為住民制定一份詳細的照護計畫：

住民資訊：
姓名：{resident.name}
年齡：{resident.age}
醫療狀況：{resident.medical_conditions or '無特殊狀況'}
當前用藥：{resident.medications or '無'}
房間號碼：{resident.room_number or '未指定'}

AI 分析結果：
{analysis_result}

額外備註：
{additional_notes}

請提供一份結構化的照護計畫，包含：
1. 日常生活照護
2. 醫療照護
3. 安全措施
4. 社交與娛樂活動
5. 特殊注意事項
6. 緊急應對程序

每項都請提供具體、可執行的指導。
"""
            }
        ]
        
        care_plan = call_deepseek_api(messages, max_tokens=3000)
        
        # 更新住民的當前照護計畫
        resident.current_care_plan = care_plan
        resident.updated_at = datetime.utcnow()
        
        # 保存到歷史記錄
        history = CarePlanHistory(
            title=f"AI 生成照護計畫 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            content=care_plan,
            ai_suggestions=analysis_result,
            resident_id=resident_id,
            version=len(resident.care_plan_history) + 1
        )
        
        db.session.add(history)
        db.session.commit()
        
        current_user.increment_usage()
        
        return api_response(True, data={
            "care_plan": care_plan,
            "care_plan_history_id": history.id,
            "remaining_usage": current_user.get_remaining_usage()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Care plan generation error: {str(e)}")
        return api_response(False, error={"message": f"Care plan generation failed: {str(e)}"}, status_code=500)

# --- Care Plan History API ---

@api_v1.route('/residents/<int:resident_id>/care-plan', methods=['GET'])
@login_required
def get_current_care_plan(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        return api_response(True, data={
            "current_care_plan": resident.current_care_plan,
            "last_updated": resident.updated_at.isoformat() if resident.updated_at else None
        })
    except Exception as e:
        current_app.logger.error(f"Get care plan error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch care plan"}, status_code=500)

@api_v1.route('/residents/<int:resident_id>/care-plan', methods=['POST'])
@login_required
def save_care_plan(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        data = request.get_json()
        care_plan = data.get('care_plan')
        title = data.get('title', f"手動更新照護計畫 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        if not care_plan:
            return api_response(False, error={"message": "Care plan content is required"}, status_code=400)
        
        # 更新當前照護計畫
        resident.current_care_plan = care_plan
        resident.updated_at = datetime.utcnow()
        
        # 保存到歷史記錄
        history = CarePlanHistory(
            title=title,
            content=care_plan,
            resident_id=resident_id,
            version=len(resident.care_plan_history) + 1
        )
        
        db.session.add(history)
        db.session.commit()
        
        return api_response(True, data={
            "care_plan_history_id": history.id,
            "message": "Care plan saved successfully"
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Save care plan error: {str(e)}")
        return api_response(False, error={"message": "Failed to save care plan"}, status_code=500)

@api_v1.route('/residents/<int:resident_id>/care-plan/history', methods=['GET'])
@login_required
def get_care_plan_history(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        history = CarePlanHistory.query.filter_by(resident_id=resident_id).order_by(CarePlanHistory.created_at.desc()).all()
        return api_response(True, data=[h.to_dict() for h in history])
    except Exception as e:
        current_app.logger.error(f"Get care plan history error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch care plan history"}, status_code=500)

@api_v1.route('/care-plan-history/<int:history_id>', methods=['GET'])
@login_required
def get_care_plan_history_detail(history_id):
    try:
        history = CarePlanHistory.query.join(Resident).filter(
            CarePlanHistory.id == history_id,
            Resident.owner_id == current_user.id
        ).first()
        
        if not history:
            return api_response(False, error={"message": "Care plan history not found"}, status_code=404)
        
        return api_response(True, data=history.to_dict())
    except Exception as e:
        current_app.logger.error(f"Get care plan history detail error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch care plan history"}, status_code=500)

# --- Care Tasks API ---

@api_v1.route('/residents/<int:resident_id>/tasks', methods=['POST'])
@login_required
def create_care_tasks(resident_id):
    try:
        resident = Resident.query.filter_by(id=resident_id, owner_id=current_user.id).first()
        if not resident:
            return api_response(False, error={"message": "Resident not found"}, status_code=404)
        
        data = request.get_json()
        tasks_data = data.get('tasks', [])
        
        if not tasks_data:
            return api_response(False, error={"message": "Tasks data is required"}, status_code=400)
        
        created_tasks = []
        for task_data in tasks_data:
            task = CareTask(
                title=task_data.get('title'),
                description=task_data.get('description'),
                priority=task_data.get('priority', 'medium'),
                due_date=datetime.strptime(task_data.get('due_date'), '%Y-%m-%d %H:%M') if task_data.get('due_date') else None,
                assigned_to=task_data.get('assigned_to'),
                resident_id=resident_id
            )
            db.session.add(task)
            created_tasks.append(task)
        
        db.session.commit()
        
        return api_response(True, data=[task.to_dict() for task in created_tasks], status_code=201)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create care tasks error: {str(e)}")
        return api_response(False, error={"message": "Failed to create care tasks"}, status_code=500)

@api_v1.route('/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_care_task(task_id):
    try:
        task = CareTask.query.join(Resident).filter(
            CareTask.id == task_id,
            Resident.owner_id == current_user.id
        ).first()
        
        if not task:
            return api_response(False, error={"message": "Task not found"}, status_code=404)
        
        data = request.get_json()
        
        # 更新允許的字段
        for field in ['title', 'description', 'priority', 'status', 'assigned_to', 'notes']:
            if field in data:
                setattr(task, field, data[field])
        
        if 'due_date' in data and data['due_date']:
            task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d %H:%M')
        
        if data.get('status') == 'completed' and not task.completed_at:
            task.completed_at = datetime.utcnow()
        elif data.get('status') != 'completed':
            task.completed_at = None
        
        task.updated_at = datetime.utcnow()
        db.session.commit()
        
        return api_response(True, data=task.to_dict())
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Update care task error: {str(e)}")
        return api_response(False, error={"message": "Failed to update care task"}, status_code=500)

# --- Shareable Links API ---

@api_v1.route('/shares', methods=['POST'])
@login_required
def create_shareable_link():
    try:
        data = request.get_json()
        password = data.get('password')
        resident_ids = data.get('resident_ids', [])
        title = data.get('title', 'Care Dashboard')
        description = data.get('description', '')
        expires_in_days = data.get('expires_in_days', 30)

        if not password or not resident_ids:
            return api_response(False, error={"message": "Password and at least one resident ID are required"}, status_code=400)

        # 驗證住民屬於當前用戶
        residents = Resident.query.filter(
            Resident.id.in_(resident_ids),
            Resident.owner_id == current_user.id
        ).all()
        
        if len(residents) != len(resident_ids):
            return api_response(False, error={"message": "One or more resident IDs are invalid"}, status_code=404)

        expires_date = datetime.utcnow() + timedelta(days=expires_in_days)

        link = ShareableLink(
            title=title,
            description=description,
            expires_date=expires_date,
            created_by=current_user.id
        )
        link.set_password(password)
        link.residents.extend(residents)
        
        db.session.add(link)
        db.session.commit()
        
        share_url = f"{request.host_url}shared/{link.share_token}"
        
        return api_response(True, data={
            "share_url": share_url,
            "link": link.to_dict()
        }, status_code=201)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Create shareable link error: {str(e)}")
        return api_response(False, error={"message": "Failed to create shareable link"}, status_code=500)

@api_v1.route('/shares/<string:share_token>/meta', methods=['GET'])
def get_share_meta(share_token):
    try:
        link = ShareableLink.query.filter_by(share_token=share_token, is_active=True).first()
        if not link or link.is_expired():
            return api_response(False, error={"message": "Link is invalid or has expired"}, status_code=404)
        
        return api_response(True, data={
            "title": link.title,
            "description": link.description,
            "is_expired": link.is_expired()
        })
    except Exception as e:
        current_app.logger.error(f"Get share meta error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch share metadata"}, status_code=500)

@api_v1.route('/shares/<string:share_token>/authenticate', methods=['POST'])
def authenticate_share_access(share_token):
    try:
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            return api_response(False, error={"message": "Password is required"}, status_code=400)
        
        link = ShareableLink.query.filter_by(share_token=share_token, is_active=True).first()

        if not link or link.is_expired():
            return api_response(False, error={"message": "Link is invalid or has expired"}, status_code=404)

        if link.check_password(password):
            link.increment_access()
            # TODO: 未來實現 JWT token
            return api_response(True, data={"message": "Authentication successful"})
        else:
            return api_response(False, error={"message": "Incorrect password"}, status_code=401)
            
    except Exception as e:
        current_app.logger.error(f"Authenticate share access error: {str(e)}")
        return api_response(False, error={"message": "Authentication failed"}, status_code=500)

@api_v1.route('/shares/<string:share_token>/dashboard', methods=['GET'])
def get_shared_dashboard_data(share_token):
    try:
        # TODO: 未來需要 JWT 驗證
        link = ShareableLink.query.filter_by(share_token=share_token, is_active=True).first()
        if not link or link.is_expired():
            return api_response(False, error={"message": "Link is invalid or has expired"}, status_code=404)

        dashboard_data = [resident.to_dict(include_tasks=True) for resident in link.residents]
        return api_response(True, data={
            "dashboard_title": link.title,
            "residents": dashboard_data
        })
    except Exception as e:
        current_app.logger.error(f"Get shared dashboard error: {str(e)}")
        return api_response(False, error={"message": "Failed to fetch shared dashboard"}, status_code=500) 