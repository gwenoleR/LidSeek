from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Artist(Base):
    __tablename__ = 'artists'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    added_date = Column(DateTime, default=datetime.utcnow)
    albums = relationship('Album', back_populates='artist')

class Album(Base):
    __tablename__ = 'albums'
    id = Column(String, primary_key=True)
    artist_id = Column(String, ForeignKey('artists.id'), nullable=False)
    title = Column(String, nullable=False)
    release_date = Column(String)
    cover_url = Column(Text)
    status = Column(String, default='pending')
    added_date = Column(DateTime, default=datetime.utcnow)
    download_date = Column(DateTime)
    source_username = Column(String)
    artist = relationship('Artist', back_populates='albums')
    tracks = relationship('Track', back_populates='album')
    blacklist_sources = relationship('AlbumBlacklistSource', back_populates='album')

class Track(Base):
    __tablename__ = 'tracks'
    id = Column(String, primary_key=True)
    album_id = Column(String, ForeignKey('albums.id'), nullable=False)
    title = Column(String, nullable=False)
    position = Column(String)
    length = Column(Integer)
    status = Column(String, default='pending')
    added_date = Column(DateTime, default=datetime.utcnow)
    download_date = Column(DateTime)
    local_path = Column(Text)
    slsk_id = Column(String)
    artist = Column(String)
    album_name = Column(String)  # anciennement 'album'
    track = Column(String)
    disc = Column(String)
    year = Column(String)
    albumartist = Column(String)
    album = relationship('Album', back_populates='tracks')

class AlbumBlacklistSource(Base):
    __tablename__ = 'album_blacklist_sources'
    album_id = Column(String, ForeignKey('albums.id'), primary_key=True)
    username = Column(String, primary_key=True)
    added_date = Column(DateTime, default=datetime.utcnow)
    album = relationship('Album', back_populates='blacklist_sources')
