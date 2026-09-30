"""Bağlam oluşturucu (Context Builder)."""

from game_designer.models.query import RetrievedChunk
from game_designer.models.user_profile import UserProfile


class ContextBuilder:
    """RAG modeline iletilecek bağlam bloklarını ve sistem talimatlarını inşa eden sınıf."""

    def build_context(
        self,
        chunks: list[RetrievedChunk],
        user_profile: UserProfile | None = None,
        extra_context: dict | None = None,
    ) -> str:
        """Alınan chunk'ları ve kullanıcı profilini tek bir bağlam metnine dönüştürür.

        Args:
            chunks: Vektör aramadan gelen döküman parçaları.
            user_profile: Kullanıcı profil bilgisi (varsa).
            extra_context: Ek parametreler.

        Returns:
            Biçimlendirilmiş context metni.
        """
        parts: list[str] = []

        # 1. Bilgi tabanı parçaları
        if chunks:
            parts.append("=== DOĞRULANMIŞ BİLGİ TABANI KAYNAKLARI ===")
            for idx, c in enumerate(chunks, 1):
                meta = c.metadata
                source_info = f"[KAYNAK {idx}] '{meta.source_title}' | Kategori: {meta.category.value} | Güvenilirlik: Tier {meta.reliability_tier}/5"
                if meta.author:
                    source_info += f" | Yazar: {meta.author}"
                if meta.game_engines:
                    source_info += f" | Motorlar: {', '.join(meta.game_engines)}"
                
                parts.append(f"{source_info}\nİçerik:\n{c.text}\n")
        else:
            parts.append("=== DOĞRULANMIŞ BİLGİ TABANI KAYNAKLARI ===\n(Bu konu hakkında bilgi tabanında kayıtlı chunk bulunamadı.)\n")

        # 2. Kullanıcı ve aktif proje bilgisi
        if user_profile:
            profile_lines = ["=== KULLANICI & PROJE PROFİLİ ==="]
            profile_lines.append(f"Geliştirici Seviyesi: {user_profile.experience_level}")
            if user_profile.preferred_game_engines:
                profile_lines.append(f"Tercih Edilen Motorlar: {', '.join(user_profile.preferred_game_engines)}")
            if user_profile.preferred_genres:
                profile_lines.append(f"İlgilenilen Türler: {', '.join(user_profile.preferred_genres)}")

            if user_profile.active_project:
                proj = user_profile.active_project
                profile_lines.append(f"Aktif Proje: {proj.project_name}")
                if proj.game_engine:
                    profile_lines.append(f"  Motor: {proj.game_engine}")
                if proj.genre:
                    profile_lines.append(f"  Tür: {proj.genre}")
                if proj.development_phase:
                    profile_lines.append(f"  Geliştirme Aşaması: {proj.development_phase}")
                if proj.key_features:
                    profile_lines.append(f"  Temel Özellikler: {', '.join(proj.key_features)}")
                if proj.known_challenges:
                    profile_lines.append(f"  Zorluklar/Sorunlar: {', '.join(proj.known_challenges)}")
                if proj.notes:
                    profile_lines.append(f"  Notlar: {proj.notes}")

            parts.append("\n".join(profile_lines) + "\n")

        # 3. Ek bağlam
        if extra_context:
            extra_lines = ["=== EK ÇALIŞMA BAĞLAMI ==="]
            for k, v in extra_context.items():
                extra_lines.append(f"{k}: {v}")
            parts.append("\n".join(extra_lines) + "\n")

        return "\n".join(parts)
