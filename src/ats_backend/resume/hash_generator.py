"""Candidate hash generation for duplicate detection."""

import hashlib
from typing import Dict, Optional
import re
import structlog

logger = structlog.get_logger(__name__)


class CandidateHashGenerator:
    """Generate consistent hashes for candidate duplicate detection."""
    
    def __init__(self):
        """Initialize hash generator."""
        pass
    
    def generate_candidate_hash(
        self,
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> str:
        """Generate a hash for candidate duplicate detection.
        
        Args:
            name: Candidate name
            email: Candidate email
            phone: Candidate phone
            
        Returns:
            SHA-256 hash string for duplicate detection
        """
        # Normalize the input data
        normalized_name = self._normalize_name(name) if name else ""
        normalized_email = self._normalize_email(email) if email else ""
        normalized_phone = self._normalize_phone(phone) if phone else ""
        
        # Create a consistent string for hashing
        hash_input = f"{normalized_name}|{normalized_email}|{normalized_phone}"
        
        # Generate SHA-256 hash
        hash_object = hashlib.sha256(hash_input.encode('utf-8'))
        candidate_hash = hash_object.hexdigest()
        
        logger.debug(
            "Generated candidate hash",
            name=name,
            email=email,
            phone=phone,
            normalized_input=hash_input,
            hash=candidate_hash[:16] + "..."  # Log only first 16 chars for privacy
        )
        
        return candidate_hash
    
    def generate_hash_from_dict(self, candidate_data: Dict[str, str]) -> str:
        """Generate hash from candidate data dictionary.
        
        Args:
            candidate_data: Dictionary with candidate information
            
        Returns:
            SHA-256 hash string for duplicate detection
        """
        return self.generate_candidate_hash(
            name=candidate_data.get("name"),
            email=candidate_data.get("email"),
            phone=candidate_data.get("phone")
        )
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for consistent hashing.
        
        Args:
            name: Raw name string
            
        Returns:
            Normalized name string
        """
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common prefixes/suffixes
        prefixes = ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.']
        suffixes = ['jr.', 'sr.', 'ii', 'iii', 'iv']
        
        words = normalized.split()
        
        # Remove prefixes
        if words and words[0] in prefixes:
            words = words[1:]
        
        # Remove suffixes
        if words and words[-1] in suffixes:
            words = words[:-1]
        
        # Join back
        normalized = ' '.join(words)
        
        # Remove special characters except spaces
        normalized = re.sub(r'[^a-z\s]', '', normalized)
        
        return normalized.strip()
    
    def _normalize_email(self, email: str) -> str:
        """Normalize email for consistent hashing.
        
        Args:
            email: Raw email string
            
        Returns:
            Normalized email string
        """
        if not email:
            return ""
        
        # Convert to lowercase and strip
        normalized = email.lower().strip()
        
        # Remove dots from Gmail addresses (gmail ignores dots)
        if '@gmail.com' in normalized:
            local_part, domain = normalized.split('@', 1)
            local_part = local_part.replace('.', '')
            normalized = f"{local_part}@{domain}"
        
        # Remove plus addressing (everything after + in local part)
        if '+' in normalized:
            local_part, domain = normalized.split('@', 1)
            if '+' in local_part:
                local_part = local_part.split('+')[0]
                normalized = f"{local_part}@{domain}"
        
        return normalized
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for consistent hashing.
        
        Args:
            phone: Raw phone string
            
        Returns:
            Normalized phone string (digits only)
        """
        if not phone:
            return ""
        
        # Extract only digits
        digits_only = re.sub(r'[^\d]', '', phone)
        
        # Handle Indian phone numbers
        if len(digits_only) == 10:
            # Assume Indian mobile number, add country code
            return f"91{digits_only}"
        elif len(digits_only) == 12 and digits_only.startswith('91'):
            # Already has Indian country code
            return digits_only
        elif len(digits_only) == 13 and digits_only.startswith('091'):
            # Remove leading 0 from country code
            return digits_only[1:]
        elif len(digits_only) > 10:
            # For international numbers, take last 10 digits
            return digits_only[-10:]
        
        return digits_only
    
    def calculate_similarity_score(
        self,
        candidate1: Dict[str, Optional[str]],
        candidate2: Dict[str, Optional[str]]
    ) -> float:
        """Calculate similarity score between two candidates.
        
        Args:
            candidate1: First candidate data
            candidate2: Second candidate data
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        score = 0.0
        total_weight = 0.0
        
        # Name similarity (weight: 0.4)
        name1 = self._normalize_name(candidate1.get("name", ""))
        name2 = self._normalize_name(candidate2.get("name", ""))
        if name1 and name2:
            name_score = self._calculate_string_similarity(name1, name2)
            score += name_score * 0.4
            total_weight += 0.4
        
        # Email similarity (weight: 0.4)
        email1 = self._normalize_email(candidate1.get("email", ""))
        email2 = self._normalize_email(candidate2.get("email", ""))
        if email1 and email2:
            email_score = 1.0 if email1 == email2 else 0.0
            score += email_score * 0.4
            total_weight += 0.4
        
        # Phone similarity (weight: 0.2)
        phone1 = self._normalize_phone(candidate1.get("phone", ""))
        phone2 = self._normalize_phone(candidate2.get("phone", ""))
        if phone1 and phone2:
            phone_score = 1.0 if phone1 == phone2 else 0.0
            score += phone_score * 0.2
            total_weight += 0.2
        
        # Return normalized score
        return score / total_weight if total_weight > 0 else 0.0
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using multiple algorithms.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not str1 or not str2:
            return 0.0
        
        if str1 == str2:
            return 1.0
        
        # Use multiple similarity algorithms and take the best score
        scores = []
        
        # Try fuzzywuzzy for advanced string similarity
        try:
            from fuzzywuzzy import fuzz
            
            # Ratio: basic similarity
            scores.append(fuzz.ratio(str1, str2) / 100.0)
            
            # Partial ratio: substring matching
            scores.append(fuzz.partial_ratio(str1, str2) / 100.0)
            
            # Token sort ratio: order-independent word matching
            scores.append(fuzz.token_sort_ratio(str1, str2) / 100.0)
            
            # Token set ratio: set-based word matching
            scores.append(fuzz.token_set_ratio(str1, str2) / 100.0)
            
        except ImportError:
            # Fallback to simple algorithms if fuzzywuzzy not available
            pass
        
        # Jaro-Winkler similarity (good for names)
        scores.append(self._jaro_winkler_similarity(str1, str2))
        
        # Levenshtein distance based similarity
        scores.append(self._levenshtein_similarity(str1, str2))
        
        # Return the maximum score from all algorithms
        return max(scores) if scores else 0.0
    
    def _jaro_winkler_similarity(self, str1: str, str2: str) -> float:
        """Calculate Jaro-Winkler similarity (good for names).
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            # Try using jellyfish library if available
            import jellyfish
            return jellyfish.jaro_winkler_similarity(str1, str2)
        except ImportError:
            # Fallback to simple Jaro similarity implementation
            return self._simple_jaro_similarity(str1, str2)
    
    def _simple_jaro_similarity(self, str1: str, str2: str) -> float:
        """Simple Jaro similarity implementation.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 == str2:
            return 1.0
        
        len1, len2 = len(str1), len(str2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Maximum allowed distance for matching characters
        match_distance = max(len1, len2) // 2 - 1
        if match_distance < 0:
            match_distance = 0
        
        # Arrays to track matches
        str1_matches = [False] * len1
        str2_matches = [False] * len2
        
        matches = 0
        transpositions = 0
        
        # Find matches
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            
            for j in range(start, end):
                if str2_matches[j] or str1[i] != str2[j]:
                    continue
                str1_matches[i] = True
                str2_matches[j] = True
                matches += 1
                break
        
        if matches == 0:
            return 0.0
        
        # Count transpositions
        k = 0
        for i in range(len1):
            if not str1_matches[i]:
                continue
            while not str2_matches[k]:
                k += 1
            if str1[i] != str2[k]:
                transpositions += 1
            k += 1
        
        # Calculate Jaro similarity
        jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0
        return jaro
    
    def _levenshtein_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity based on Levenshtein distance.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 == str2:
            return 1.0
        
        len1, len2 = len(str1), len(str2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Create distance matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        # Fill the matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i - 1] == str2[j - 1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,      # deletion
                    matrix[i][j - 1] + 1,      # insertion
                    matrix[i - 1][j - 1] + cost # substitution
                )
        
        # Convert distance to similarity
        max_len = max(len1, len2)
        distance = matrix[len1][len2]
        return 1.0 - (distance / max_len)
    
    def is_potential_duplicate(
        self,
        candidate1: Dict[str, Optional[str]],
        candidate2: Dict[str, Optional[str]],
        threshold: float = 0.8
    ) -> bool:
        """Check if two candidates are potential duplicates.
        
        Args:
            candidate1: First candidate data
            candidate2: Second candidate data
            threshold: Similarity threshold for duplicate detection
            
        Returns:
            True if candidates are potential duplicates
        """
        similarity = self.calculate_similarity_score(candidate1, candidate2)
        return similarity >= threshold