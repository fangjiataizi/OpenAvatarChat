
import os
import json
import time
from typing import Dict, Optional, List, Any
from loguru import logger
from pydantic import BaseModel, Field
from abc import ABC
from openai import OpenAI

from chat_engine.contexts.handler_context import HandlerContext
from chat_engine.data_models.chat_engine_config_data import ChatEngineConfigModel, HandlerBaseConfigModel
from chat_engine.common.handler_base import HandlerBase, HandlerBaseInfo, HandlerDataInfo, HandlerDetail
from chat_engine.data_models.chat_data.chat_data_model import ChatData
from chat_engine.data_models.chat_data_type import ChatDataType
from chat_engine.contexts.session_context import SessionContext
from chat_engine.data_models.runtime_data.data_bundle import DataBundle, DataBundleDefinition, DataBundleEntry


class LLMOption(BaseModel):
    name: str
    provider: str
    model_name: str
    system_prompt: str
    api_url: str
    api_key: str


class NewsScriptConfig(HandlerBaseConfigModel, BaseModel):
    enabled: bool = Field(default=True)
    llm_options: List[LLMOption] = Field(default_factory=list)


class NewsScriptContext(HandlerContext):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.config = None
        self.selected_llm = None
        self.client = None
        self.news_content = ""
        self.generated_script = ""
        self.script_metadata = {}


class HandlerNewsScript(HandlerBase, ABC):
    def __init__(self):
        super().__init__()
        self.llm_options = []
        self.current_client = None

    def get_handler_info(self) -> HandlerBaseInfo:
        return HandlerBaseInfo(
            name="NewsScriptGenerator",
            display_name="新闻脚本生成器",
            description="基于LLM生成适合播报的新闻脚本",
            version="1.0.0",
            author="News Broadcast Team"
        )

    def get_handler_detail(self) -> HandlerDetail:
        return HandlerDetail(
            input_data_types=[ChatDataType.HUMAN_TEXT],
            output_data_types=[ChatDataType.AVATAR_TEXT],
            consume_mode=ChatDataConsumeMode.MULTIPLE
        )

    def get_handler_data_info(self) -> HandlerDataInfo:
        return HandlerDataInfo(
            input_descriptions=["新闻内容文本"],
            output_descriptions=["生成的播报脚本"]
        )

    def create_context(self, session_id: str) -> NewsScriptContext:
        return NewsScriptContext(session_id)

    def init_handler(self, handler_config: NewsScriptConfig, chat_engine_config: ChatEngineConfigModel):
        logger.info("初始化新闻脚本生成器处理器")
        self.llm_options = handler_config.llm_options
        logger.info(f"已配置 {len(self.llm_options)} 个LLM选项")

    def select_llm_provider(self, provider_name: str, context: NewsScriptContext) -> bool:
        """选择指定的LLM提供商"""
        for option in self.llm_options:
            if option.name == provider_name:
                context.selected_llm = option

                # 创建OpenAI客户端
                self.current_client = OpenAI(
                    api_key=option.api_key,
                    base_url=option.api_url
                )
                context.client = self.current_client

                logger.info(f"已选择LLM提供商: {provider_name} ({option.provider})")
                return True

        logger.error(f"未找到LLM提供商: {provider_name}")
        return False

    def generate_news_script(self, news_content: str, context: NewsScriptContext,
                            category: str = "general", style: str = "formal") -> str:
        """生成新闻播报脚本"""
        if not context.selected_llm or not context.client:
            logger.error("未选择LLM提供商")
            return ""

        try:
            # 构建提示词
            system_prompt = context.selected_llm.system_prompt

            # 根据新闻类型调整提示
            category_prompts = {
                "politics": "这是时政新闻，请用正式、客观的语气撰写",
                "finance": "这是财经新闻，请用专业、精准的语言撰写",
                "technology": "这是科技新闻，请生动地展现创新性",
                "sports": "这是体育新闻，请用激情的语言描述",
                "life": "这是生活新闻，请用亲切的语气讲述"
            }

            category_instruction = category_prompts.get(category, "这是综合新闻")

            # 根据播报风格调整
            style_instructions = {
                "formal": "语气正式严肃，适合重大新闻播报",
                "friendly": "语气亲切自然，适合民生新闻",
                "lively": "语气生动活泼，适合娱乐体育新闻"
            }

            style_instruction = style_instructions.get(style, "语气适中")

            user_prompt = f"""
请根据以下新闻内容，生成一段适合AI数字人播报的新闻脚本。

新闻类型：{category_instruction}
播报风格：{style_instruction}

重要要求：
1. 只输出纯播报文本，不要添加任何导播指令
2. 不要包含"画面切换到"、"停顿"、"镜头"等制作指令
3. 不要包含[音乐]、[画外音]等标记
4. 语言自然流畅，适合数字人朗读
5. 控制在200-400字之间
6. 结构完整：开头问候+新闻内容+结尾致谢

新闻内容：
{news_content}

请直接输出干净的播报文本，无需其他格式。
"""

            # 调用LLM生成脚本
            logger.info(f"正在使用 {context.selected_llm.name} 生成新闻脚本")

            completion = context.client.chat.completions.create(
                model=context.selected_llm.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            script = completion.choices[0].message.content.strip()
            
            # 清理脚本中的导播指令和多余内容
            script = self._clean_script_content(script)

            # 保存元数据
            context.script_metadata = {
                "llm_provider": context.selected_llm.name,
                "model": context.selected_llm.model_name,
                "category": category,
                "style": style,
                "generated_at": time.time(),
                "word_count": len(script)
            }

            context.generated_script = script
            logger.info(f"新闻脚本生成成功，长度: {len(script)} 字符")

            return script

        except Exception as e:
            logger.error(f"新闻脚本生成失败: {str(e)}")
            return ""
    
    def _clean_script_content(self, script: str) -> str:
        """清理脚本中的导播指令和不需要的内容"""
        import re
        
        # 需要移除的模式
        patterns_to_remove = [
            r'画面切换到[^。]*。?',
            r'镜头[转切][向到][^。]*。?',
            r'特写[^。]*。?',
            r'停顿[^。]*。?',
            r'音乐[^。]*。?',
            r'\[.*?\]',  # 方括号标记
            r'（.*?停顿.*?）',  # 停顿提示
            r'（.*?画面.*?）',  # 画面提示
            r'（.*?镜头.*?）',  # 镜头提示
            r'【.*?】',  # 【标记】
            r'主播：',  # 主播标签
            r'播音员：',  # 播音员标签
        ]
        
        cleaned_script = script
        
        # 逐个清理匹配的模式
        for pattern in patterns_to_remove:
            cleaned_script = re.sub(pattern, '', cleaned_script, flags=re.IGNORECASE)
        
        # 清理多余的空白和标点
        cleaned_script = re.sub(r'\s+', ' ', cleaned_script)  # 多个空格变成一个
        cleaned_script = re.sub(r'。+', '。', cleaned_script)  # 多个句号变成一个
        cleaned_script = re.sub(r'，+', '，', cleaned_script)  # 多个逗号变成一个
        cleaned_script = cleaned_script.strip()
        
        # 记录清理前后的变化
        if cleaned_script != script:
            logger.info(f"脚本清理完成，原长度: {len(script)}, 清理后: {len(cleaned_script)}")
            removed_content = len(script) - len(cleaned_script)
            if removed_content > 10:  # 只有当移除内容较多时才记录
                logger.info(f"移除了 {removed_content} 个字符的导播指令")
        
        return cleaned_script

    def process_data(self, data: ChatData, context: NewsScriptContext) -> Optional[ChatData]:
        """处理输入数据"""
        try:
            # 解析输入数据
            if data.type == ChatDataType.HUMAN_TEXT:
                news_content = data.data.get("text", "")
                category = data.data.get("category", "general")
                style = data.data.get("style", "formal")
                llm_provider = data.data.get("llm_provider", "qwen-plus")

                # 选择LLM提供商
                if not self.select_llm_provider(llm_provider, context):
                    return None

                # 生成脚本
                script = self.generate_news_script(news_content, context, category, style)

                if script:
                    # 返回生成的脚本
                    output_data = ChatData(
                        type=ChatDataType.AVATAR_TEXT,
                        data={
                            "text": script,
                            "script_type": "news_broadcast",
                            "metadata": context.script_metadata,
                            "original_content": news_content
                        }
                    )
                    return output_data

            return None

        except Exception as e:
            logger.error(f"新闻脚本处理器处理数据失败: {str(e)}")
            return None

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """获取可用的LLM提供商列表"""
        return [
            {
                "name": option.name,
                "provider": option.provider,
                "model_name": option.model_name,
                "description": f"{option.provider} - {option.model_name}"
            }
            for option in self.llm_options
        ]

    def load(self, engine_config: ChatEngineConfigModel, handler_config: Optional[HandlerBaseConfigModel] = None):
        """加载处理器"""
        logger.info("加载新闻脚本生成处理器")
        return True

    def start_context(self, session_context: SessionContext, handler_context: HandlerContext):
        """启动上下文"""
        logger.info(f"启动新闻脚本生成上下文: {handler_context.session_id}")
        return True

    def handle(self, context: HandlerContext, inputs: ChatData,
              session_context: SessionContext) -> Optional[ChatData]:
        """处理数据"""
        logger.info(f"处理新闻脚本生成数据: {inputs.data_type}")
        return self.process_data(inputs, context)

    def destroy_context(self, context: HandlerContext):
        """销毁上下文"""
        logger.info(f"销毁新闻脚本生成上下文: {context.session_id}")
        return True
