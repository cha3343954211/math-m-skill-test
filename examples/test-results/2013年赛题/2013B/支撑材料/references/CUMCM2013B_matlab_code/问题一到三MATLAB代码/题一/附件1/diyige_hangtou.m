function [tou] = diyige_hangtou(cell)


for i = 1:length(cell)
    if cell{1,i}(:,1) == 255
        tou = i;
    end
end


end

