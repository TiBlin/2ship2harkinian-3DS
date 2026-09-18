#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace Blinky {
inline int8_t Axis(int value,int deadzone,int extent=156) {
    deadzone=std::clamp(deadzone,0,extent-1);
    int magnitude=std::abs(value);
    if(magnitude<=deadzone)return 0;
    int scaled=std::min(85,(magnitude-deadzone)*85/(extent-deadzone));
    return static_cast<int8_t>(value<0?-scaled:scaled);
}
inline void LimitStick(int8_t& x,int8_t& y) {
    // N64 cardinal limit is 85; diagonal directions are limited radially.
    float radius=std::hypot(float(x),float(y));
    if(radius>85){x=std::lround(x*85/radius);y=std::lround(y*85/radius);}
}
template<class Pad,class Native> void MergePad(Pad& to,const Native& from) {
    to.button|=from.buttons;
    if(!to.stick_x)to.stick_x=from.x;
    if(!to.stick_y)to.stick_y=from.y;
    if(!to.right_stick_x)to.right_stick_x=from.cx;
    if(!to.right_stick_y)to.right_stick_y=from.cy;
    if(!to.gyro_x)to.gyro_x=from.gyroX;
    if(!to.gyro_y)to.gyro_y=from.gyroY;
}
}
