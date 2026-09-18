// A deliberately bounded pixel model for opaque triangles with nearest sampled
// textures. This is not PICA emulation. The independent coordinate contract is:
// raster (x,y) -> Morton(x, allocationHeight-1-y), and texture (u,v) ->
// Morton(floor(u*allocationWidth), allocationHeight-1-floor(v*allocationHeight)).
// See official tex3ds load_image/process_image and Citro3D Mtx_OrthoTilt.
namespace orientationTest {
constexpr unsigned Width=13,Height=9;
constexpr uint32_t Sentinel=0x5a6b7c8d;
static unsigned checks=0;
static void Require(bool condition,const char* message) {
    ++checks;
    if(!condition){std::fprintf(stderr,"FAIL orientation: %s\n",message);std::exit(87);}
}
static size_t Morton(unsigned x,unsigned y,unsigned pitch) {
    unsigned local=0;
    for(unsigned bit=0;bit<3;++bit) {
        local|=((x>>bit)&1)<<(2*bit);
        local|=((y>>bit)&1)<<(2*bit+1);
    }
    return ((y/8)*(pitch/8)+x/8)*64+local;
}
static Blinky::Color Pattern(unsigned x,unsigned topY) {
    static const Blinky::Color corners[4]={{1,0,0,1},{0,1,0,1},{0,0,1,1},{1,1,1,1}};
    return corners[(topY>=4)*2+(x>=6)];
}
static Blinky::Color ReadRaw(const C3D_FrameBuf& fb,unsigned x,unsigned rawY) {
    auto* pixel=static_cast<const unsigned char*>(fb.colorBuf)+Morton(x,rawY,fb.width)*4;
    return {pixel[3]/255.f,pixel[2]/255.f,pixel[1]/255.f,pixel[0]/255.f};
}
static Blinky::Color Sample(const C3D_Tex& texture,float u,float v) {
    unsigned x=std::clamp(int(std::floor(u*texture.width)),0,int(texture.width)-1);
    unsigned y=std::clamp(int(std::floor(v*texture.height)),0,int(texture.height)-1);
    auto* pixel=static_cast<const unsigned char*>(texture.data)+Morton(x,texture.height-1-y,texture.width)*4;
    return {pixel[3]/255.f,pixel[2]/255.f,pixel[1]/255.f,pixel[0]/255.f};
}
static void Raster(const float* data,size_t count,C3D_RenderTarget* target,const std::array<int,4>& viewport) {
    Require(target!=nullptr,"draw target captured");
    auto& fb=target->frameBuf;
    auto edge=[](float ax,float ay,float bx,float by,float px,float py){return (bx-ax)*(py-ay)-(by-ay)*(px-ax);};
    for(size_t first=0;first<count;first+=3) {
        const float* p[3]={data+first*14,data+(first+1)*14,data+(first+2)*14};
        float x[3],y[3];
        for(unsigned i=0;i<3;++i){x[i]=viewport[0]+(p[i][0]/p[i][3]+1)*viewport[2]/2;y[i]=viewport[1]+(p[i][1]/p[i][3]+1)*viewport[3]/2;}
        float area=edge(x[0],y[0],x[1],y[1],x[2],y[2]);
        if(std::abs(area)<1e-6f)continue;
        for(int py=viewport[1];py<viewport[1]+viewport[3];++py)for(int px=viewport[0];px<viewport[0]+viewport[2];++px) {
            float weights[3]={edge(x[1],y[1],x[2],y[2],px+.5f,py+.5f)/area,
                edge(x[2],y[2],x[0],y[0],px+.5f,py+.5f)/area,
                edge(x[0],y[0],x[1],y[1],px+.5f,py+.5f)/area};
            if(*std::min_element(weights,weights+3)<-1e-6f)continue;
            float depth=0,denominator=0;
            for(unsigned i=0;i<3;++i){depth-=weights[i]*p[i][2]/p[i][3];weights[i]/=p[i][3];denominator+=weights[i];}
            for(float& weight:weights)weight/=denominator;
            Blinky::Color primary{},texels[2]{};
            for(unsigned i=0;i<3;++i)for(unsigned lane=0;lane<4;++lane)primary[lane]+=weights[i]*p[i][4+lane];
            // These scenes bind only texture 0 and use no fog, blending or alpha test.
            if(gpuFake::bound[0]) {
                float u=0,v=0;for(unsigned i=0;i<3;++i){u+=weights[i]*p[i][8];v+=weights[i]*p[i][9];}
                texels[0]=Sample(*gpuFake::bound[0],u,v);
            }
            auto color=RunTexEnv(primary,texels);
            size_t address=Morton(px,fb.height-1-py,fb.width);
            auto* pixel=static_cast<unsigned char*>(fb.colorBuf)+address*4;
            for(unsigned lane=0;lane<4;++lane)if(gpuFake::pixel.mask&(1<<lane))pixel[3-lane]=std::lround(color[lane]*255);
            if(fb.depthBuf && (gpuFake::pixel.mask&GPU_WRITE_DEPTH))
                static_cast<uint16_t*>(fb.depthBuf)[address]=std::lround(std::clamp(depth,0.f,1.f)*65535);
        }
    }
}
static std::vector<float> Geometry(bool cpu,bool texture,bool inverted) {
    std::vector<float> result;
    const unsigned boundsX[3]={0,6,Width},boundsY[3]={0,4,Height};
    const unsigned corners[6]={0,1,2,0,2,3};
    for(unsigned row=0;row<2;++row)for(unsigned col=0;col<2;++col) {
        const float xy[4][2]={{float(boundsX[col]),float(boundsY[row+1])},
            {float(boundsX[col+1]),float(boundsY[row+1])},{float(boundsX[col+1]),float(boundsY[row])},
            {float(boundsX[col]),float(boundsY[row])}};
        for(unsigned corner:corners) {
            float x=xy[corner][0],topY=xy[corner][1],clipY=1-2*topY/Height;
            result.insert(result.end(),{2*x/Width-1,inverted?-clipY:clipY,0,1});
            if(texture)result.insert(result.end(),{x/Width,topY/Height});
            if(cpu)result.insert(result.end(),{0,0,0,0}); // zero-amount grayscale forces reference raster
            auto color=texture?Blinky::Color{1,1,1,1}:Pattern(boundsX[col],boundsY[row]);
            result.insert(result.end(),color.begin(),color.begin()+3);
        }
    }
    return result;
}
static void CheckPixels(Fast::GfxRenderingAPIBlinkyCitro3D& gpu,int target,bool inverted,const char* message) {
    std::array<uint16_t,Width*Height> pixels{};gpu.ReadFramebufferToCPU(target,Width,Height,pixels.data());
    for(unsigned y=0;y<Height;++y)for(unsigned x=0;x<Width;++x)
        Require(pixels[y*Width+x]==Blinky::Pack5551(Pattern(x,inverted?y:Height-1-y)),message);
}
static void CheckStorage(const C3D_FrameBuf& fb,bool inverted) {
    Require(fb.width==16 && fb.height==16,"non-square logical target uses padded 16x16 allocation");
    for(unsigned rawY=0;rawY<16;++rawY)for(unsigned x=0;x<16;++x) {
        size_t address=Morton(x,rawY,16);
        if(x>=Width || rawY<16-Height) {
            Require(static_cast<const uint32_t*>(fb.colorBuf)[address]==Sentinel,"padding remains sentinel");
            Require(static_cast<const uint16_t*>(fb.depthBuf)[address]==0x1234,"depth padding remains sentinel");
        } else {
            unsigned rasterY=15-rawY;
            Require(Blinky::Pack5551(ReadRaw(fb,x,rawY))==Blinky::Pack5551(Pattern(x,inverted?rasterY:Height-1-rasterY)),"physical PICA color row");
            Require(std::abs(int(static_cast<const uint16_t*>(fb.depthBuf)[address])-32768)<=1,"physical PICA depth row");
        }
    }
}
static void Run() {
    Fast::GfxRenderingAPIBlinkyCitro3D gpu;gpu.Init();gpu.StartFrame();
    gpu.UpdateFramebufferParameters(0,Width,Height,1,false,true,true,true);
    int offscreen=gpu.CreateFramebuffer();gpu.UpdateFramebufferParameters(offscreen,Width,Height,1,true,true,true,true);
    gpu.SetViewport(0,0,Width,Height);gpu.SetScissor(0,0,Width,Height);
    gpu.SetDepthTestAndMask(false,true);gpu.SetUseAlpha(false);
    auto texture=gpu.NewTexture();gpu.SelectTexture(0,texture);
    std::vector<unsigned char> pixels(Width*Height*4);
    for(unsigned y=0;y<Height;++y)for(unsigned x=0;x<Width;++x){auto c=Pattern(x,y);for(unsigned lane=0;lane<4;++lane)pixels[(y*Width+x)*4+lane]=std::lround(c[lane]*255);}
    gpu.UploadTexture(pixels.data(),Width,Height);gpu.SetSamplerParameters(0,false,2,2);
    gpuFake::rasterize=Raster;
    for(int target:{0,offscreen}) {
        bool inverted=target!=0;gpu.StartDrawToFramebuffer(target,1);
        auto clip=gpu.GetClipParameters();
        Require(!clip.z_is_from_0_to_1 && clip.invertY==inverted,"active target GetClipParameters invertY contract");
        C3D_RenderTarget* rawTarget=nullptr;
        for(bool cpu:{false,true})for(bool textured:{false,true}) {
            // Prime the draw target capture before poisoning all raw rows.
            gpu.CreateAndLoadNewShader(0x1000,uint64_t(0xffff)<<17);
            auto prime=Geometry(false,false,inverted);gpu.DrawTriangles(prime.data(),prime.size(),8);
            rawTarget=gpuFake::target;
            std::array<uint16_t,Width*Height> scratch;gpu.ReadFramebufferToCPU(target,Width,Height,scratch.data());
            std::fill_n(static_cast<uint32_t*>(rawTarget->frameBuf.colorBuf),16*16,Sentinel);
            std::fill_n(static_cast<uint16_t*>(rawTarget->frameBuf.depthBuf),16*16,0x1234);
            gpu.SelectTexture(0,texture);
            gpu.CreateAndLoadNewShader(textured?0x0108:0x1000,(uint64_t(0xffff)<<17)|(cpu?128:0));
            auto geometry=Geometry(cpu,textured,inverted);gpu.DrawTriangles(geometry.data(),geometry.size(),8);
            CheckPixels(gpu,target,inverted,textured?"asymmetric texture CPU/GPU readback":"asymmetric primary CPU/GPU readback");
            CheckStorage(rawTarget->frameBuf,inverted);
        }
        gpu.ClearDepthRegion(1,2,3,2);
        for(unsigned y=0;y<Height;++y)for(unsigned x=0;x<Width;++x) {
            uint16_t depth=static_cast<uint16_t*>(rawTarget->frameBuf.depthBuf)[Morton(x,15-y,16)];
            Require(x>=1 && x<4 && y>=2 && y<4?depth==0:std::abs(int(depth)-32768)<=1,"depth clear uses raster coordinates");
        }
    }
    // Cross-convention copies must reverse rows exactly once, and round-trip.
    gpu.CopyFramebuffer(offscreen,0,0,0,Width,Height,0,0,Width,Height);
    CheckPixels(gpu,offscreen,true,"copy false to true orientation");
    gpu.CopyFramebuffer(0,offscreen,0,0,Width,Height,0,0,Width,Height);
    CheckPixels(gpu,0,false,"copy true to false round trip");
    // Return the API's active target to main before the presentation check.
    gpu.StartDrawToFramebuffer(0,1);
    Require(!gpu.GetClipParameters().invertY,"main clip contract restored");
    gpu.UpdateFramebufferParameters(offscreen,Width,Height,1,false,true,true,true);
    gpu.StartDrawToFramebuffer(offscreen,1);Require(!gpu.GetClipParameters().invertY,"same-size target inversion update");
    gpu.StartDrawToFramebuffer(0,1);
    gpuFake::rasterize=nullptr;gpu.EndFrame();
    Require(gpuFake::submitted.size()==6*14,"presentation quad captured");
    Require(gpuFake::viewport==std::array<int,4>{0,0,240,400},"native LCD viewport");
    Require((gpuFake::outputFlags&GX_TRANSFER_FLIP_VERT(1))==0,"LCD transfer does not add another inversion");
    for(unsigned i=0;i<6;++i) {
        const float* p=gpuFake::submitted.data()+i*14;
        float screenX=(1-p[1])*.5f,screenY=(1-p[0])*.5f;
        float logicalX=p[8]*16/Width,logicalBottomY=p[9]*16/Height;
        Require(std::abs(screenX-logicalX)<1e-6f && std::abs(screenY-(1-logicalBottomY))<1e-6f,"LCD orientation and padded presentation UV");
    }
    // Sample the captured presentation texture at four non-central LCD points.
    // Bottom-origin framebuffer coordinates are converted to PICA physical rows
    // by Sample, independent of the renderer's Snapshot accessor.
    for(auto xy:std::array<std::array<unsigned,2>,4>{{{2,2},{10,2},{2,7},{10,7}}}) {
        float u=(xy[0]+.5f)/16,v=(Height-xy[1]-.5f)/16;
        Require(Blinky::Pack5551(Sample(*gpuFake::bound[0],u,v))==Blinky::Pack5551(Pattern(xy[0],xy[1])),"four named LCD corner colors");
    }
    std::printf("PASS orientation: %u asymmetric CPU/GPU, raw PICA padding/color/depth, texture, offscreen/copy and LCD checks\n",checks);
}
}
static void OrientationRegression(){orientationTest::Run();}
