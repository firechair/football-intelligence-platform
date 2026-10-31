from datetime import datetime, timedelta
from typing import Dict, Any
import re
from fastapi import Request
import hashlib
import secrets
import logging

logger = logging.getLogger(__name__)

class SecurityService:
    """Servizio per gestione sicurezza avanzata"""
    
    def __init__(self):
        # Rate limiting storage (in production use Redis)
        self.rate_limit_storage: Dict[str, Dict[str, Any]] = {}
        self.blocked_tokens: set = set()
        
        # Password policy - made less restrictive
        self.password_policy = {
            'min_length': 6,
            'require_uppercase': False,  # Made optional
            'require_lowercase': True,
            'require_digits': True,
            'require_special_chars': False,  # Made optional
            'max_length': 128
        }
    
    def validate_password_strength(self, password: str) -> Dict[str, Any]:
        """Valida la forza della password secondo policy"""
        errors = []
        score = 0
        
        # Length check
        if len(password) < self.password_policy['min_length']:
            errors.append(f"Password deve essere almeno {self.password_policy['min_length']} caratteri")
        elif len(password) >= 12:
            score += 2
        else:
            score += 1
            
        if len(password) > self.password_policy['max_length']:
            errors.append(f"Password non può superare {self.password_policy['max_length']} caratteri")
        
        # Complexity checks
        if self.password_policy['require_uppercase'] and not re.search(r'[A-Z]', password):
            errors.append("Password deve contenere almeno una lettera maiuscola")
        else:
            score += 1
            
        if self.password_policy['require_lowercase'] and not re.search(r'[a-z]', password):
            errors.append("Password deve contenere almeno una lettera minuscola")
        else:
            score += 1
            
        if self.password_policy['require_digits'] and not re.search(r'\d', password):
            errors.append("Password deve contenere almeno un numero")
        else:
            score += 1
            
        if self.password_policy['require_special_chars'] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password deve contenere almeno un carattere speciale")
        else:
            score += 1
        
        # Common patterns check - only very weak patterns
        weak_patterns = ['123456', 'qwerty', '111111', 'aaaaaa']
        if any(pattern in password.lower() for pattern in weak_patterns):
            errors.append("Password contiene sequenze troppo semplici")
            score = max(0, score - 1)
        
        # Strength levels
        if score >= 6:
            strength = "forte"
        elif score >= 4:
            strength = "media"
        elif score >= 2:
            strength = "debole"
        else:
            strength = "molto debole"
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'strength': strength,
            'score': score
        }
    
    def generate_secure_token(self, length: int = 32) -> str:
        """Genera token sicuro per refresh tokens"""
        return secrets.token_urlsafe(length)
    
    def hash_token(self, token: str) -> str:
        """Hash di un token per storage sicuro"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_rate_limited(self, key: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
        """Controllo rate limiting"""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        if key not in self.rate_limit_storage:
            self.rate_limit_storage[key] = {'attempts': [], 'blocked_until': None}
        
        storage = self.rate_limit_storage[key]
        
        # Check if currently blocked
        if storage['blocked_until'] and now < storage['blocked_until']:
            return True
        
        # Clean old attempts
        storage['attempts'] = [
            attempt for attempt in storage['attempts'] 
            if attempt > window_start
        ]
        
        # Check rate limit
        if len(storage['attempts']) >= max_attempts:
            storage['blocked_until'] = now + timedelta(minutes=window_minutes * 2)
            logger.warning(f"Rate limit exceeded for key: {key}")
            return True
        
        return False
    
    def record_attempt(self, key: str) -> None:
        """Registra tentativo per rate limiting"""
        now = datetime.now()
        if key not in self.rate_limit_storage:
            self.rate_limit_storage[key] = {'attempts': [], 'blocked_until': None}
        
        self.rate_limit_storage[key]['attempts'].append(now)
    
    def blacklist_token(self, token: str) -> None:
        """Aggiunge token alla blacklist"""
        token_hash = self.hash_token(token)
        self.blocked_tokens.add(token_hash)
        logger.info(f"Token blacklisted: {token_hash[:8]}...")
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Verifica se token è in blacklist"""
        token_hash = self.hash_token(token)
        return token_hash in self.blocked_tokens
    
    def get_client_identifier(self, request: Request) -> str:
        """Ottiene identificatore client per rate limiting"""
        # Priority: X-Forwarded-For (proxy), X-Real-IP, client IP
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def sanitize_input(self, input_str: str, max_length: int = 1000) -> str:
        """Sanitizza input utente"""
        if not input_str:
            return ""
        
        # Truncate if too long
        sanitized = input_str[:max_length]
        
        # Remove potential XSS
        dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'data:', 'vbscript:']
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized.strip()
    
    def validate_email_format(self, email: str) -> bool:
        """Valida formato email"""
        pattern = r'^[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return len(email) <= 254 and bool(re.match(pattern, email))
    
    def validate_username_format(self, username: str) -> Dict[str, Any]:
        """Valida formato username"""
        errors = []
        
        # Length check
        if len(username) < 3:
            errors.append("Username deve essere almeno 3 caratteri")
        if len(username) > 50:
            errors.append("Username non può superare 50 caratteri")
        
        # Character check
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            errors.append("Username può contenere solo lettere, numeri, punti, underscore e trattini")
        
        # Start/end check
        if username.startswith('.') or username.endswith('.'):
            errors.append("Username non può iniziare o finire con un punto")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

# Singleton instance
security_service = SecurityService()
