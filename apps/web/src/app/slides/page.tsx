"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Download, Maximize2, FileDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const mockSlides = [
  { id: 1, title: "Title Slide", section: "Introduction", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Quantum+Computing+Advances" },
  { id: 2, title: "Overview", section: "Introduction", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Research+Overview" },
  { id: 3, title: "Key Concepts", section: "Background", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Quantum+Mechanics" },
  { id: 4, title: "Methodology", section: "Methods", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Experimental+Setup" },
  { id: 5, title: "Results", section: "Results", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Data+Analysis" },
  { id: 6, title: "Discussion", section: "Discussion", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Findings" },
  { id: 7, title: "Conclusions", section: "Conclusion", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Key+Takeaways" },
  { id: 8, title: "Future Work", section: "Conclusion", imageUrl: "https://via.placeholder.com/800x600/1a1a1a/ffffff?text=Next+Steps" },
];

export default function SlidesPage() {
  const [selectedSlide, setSelectedSlide] = useState<typeof mockSlides[0] | null>(null);

  return (
    <div className="p-8 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1>Slides Preview</h1>
          <p className="text-muted-foreground mt-1">Gallery view of generated slides</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline"><FileDown className="h-4 w-4 mr-2" />Export PPTX</Button>
          <Button variant="outline"><Download className="h-4 w-4 mr-2" />Download All Images</Button>
        </div>
      </div>

      <Card className="p-6 mb-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Paper Title</div>
            <div className="mt-1">Quantum Computing Advances in 2024</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Total Slides</div>
            <div className="mt-1">{mockSlides.length}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Generation Time</div>
            <div className="mt-1">8m 24s</div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {mockSlides.map((slide) => (
          <Card key={slide.id} className="overflow-hidden group cursor-pointer">
            <div className="relative aspect-[4/3] bg-muted">
              <img src={slide.imageUrl} alt={slide.title} className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                <Button size="sm" variant="secondary" onClick={() => setSelectedSlide(slide)}>
                  <Maximize2 className="h-4 w-4 mr-2" /> View Full
                </Button>
                <Button size="sm" variant="secondary">
                  <Download className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="p-4">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="font-mono text-xs text-muted-foreground">Slide {slide.id}</div>
                <Badge variant="outline" className="text-xs">{slide.section}</Badge>
              </div>
              <div className="text-sm">{slide.title}</div>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!selectedSlide} onOpenChange={(o) => !o && setSelectedSlide(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Slide {selectedSlide?.id} - {selectedSlide?.title}</DialogTitle>
            <DialogDescription>Full size preview of {selectedSlide?.section} section slide</DialogDescription>
          </DialogHeader>
          {selectedSlide && (
            <div className="space-y-4">
              <img src={selectedSlide.imageUrl} alt={selectedSlide.title} className="w-full rounded-lg" />
              <div className="flex items-center justify-between">
                <Badge>{selectedSlide.section}</Badge>
                <Button size="sm"><Download className="h-4 w-4 mr-2" /> Download Image</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

