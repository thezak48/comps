from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class TagList(BaseModel):
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags for categorizing the comparison",
        examples=[["example", "test", "api"]]
    )

class ComparisonBase(BaseModel):
    name: Optional[str] = Field(
        None, 
        description="Internal name for the comparison",
        examples=["Example Comparison"]
    )
    show_name: Optional[str] = Field(
        None, 
        description="Display name shown in the UI",
        examples=["Example"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="List of tags for categorizing the comparison",
        examples=[["example", "test", "api"]]
    )
    total_rows: int = Field(
        1, 
        description="Number of rows in the comparison grid (max 20)",
        examples=[1]
    )
    total_columns: int = Field(
        2, 
        description="Number of columns in the comparison grid",
        examples=[2]
    )
    expiration_type: str = Field(
        "from_last_access", 
        description="When to expire the comparison: 'from_creation' or 'from_last_access'",
        examples=["from_last_access"]
    )
    expiration_days: int = Field(
        7, 
        description="Number of days until the comparison expires",
        examples=[7]
    )

class ComparisonCreate(ComparisonBase):
    pass

class ImagePosition(BaseModel):
    filename: str = Field(
        ..., 
        description="Original filename of the image",
        examples=["image1.jpg"]
    )
    row: int = Field(
        ..., 
        description="Row position in the comparison grid (0-based)",
        examples=[0]
    )
    column: int = Field(
        ..., 
        description="Column position in the comparison grid (0-based)",
        examples=[0]
    )

class ImageMetadata(BaseModel):
    original_filename: str = Field(
        ..., 
        description="Original filename of the image",
        examples=["image1.jpg"]
    )
    image_size: Optional[str] = Field(
        None, 
        description="Size of the image in bytes",
        examples=["1024 bytes"]
    )
    custom_name: Optional[str] = Field(
        None, 
        description="Custom name for the image",
        examples=["Left Image"]
    )

class Comparison(BaseModel):
    id: str
    positions: List[ImagePosition]
    metadata: Optional[dict] = None

class ComparisonResponse(ComparisonBase):
    id: str = Field(
        ..., 
        description="Unique identifier for the comparison",
        examples=["11256486-6607-4ba9-88f1-ac7cb0105e17"]
    )
    created_at: Optional[str] = Field(
        None, 
        description="Timestamp when the comparison was created",
        examples=["2023-05-01 12:34:56"]
    )
    last_accessed: Optional[str] = Field(
        None, 
        description="Timestamp when the comparison was last accessed",
        examples=["2023-05-02 10:11:12"]
    )
    
    model_config = ConfigDict(from_attributes=True)

class ImageDetail(BaseModel):
    filename: str = Field(..., description="System filename of the image", examples=["55c501a7-86a7-44b7-9aaa-333c96d38f11.jpg"])
    original_filename: Optional[str] = Field(None, description="Original filename of the image", examples=["image1.jpg"])
    custom_name: Optional[str] = Field(None, description="Custom name for the image", examples=["Left Image"])
    image_size: Optional[str] = Field(None, description="Size of the image", examples=["1024 bytes"])
    row: int = Field(..., description="Row position in the comparison grid", examples=[0])
    column: int = Field(..., description="Column position in the comparison grid", examples=[0])
    
class ComparisonDetail(ComparisonResponse):
    images: List[ImageDetail] = Field(default_factory=list)

class CustomNameUpdate(BaseModel):
    custom_name: str = Field(..., description="New custom name for the image", examples=["Updated Image Name"])
